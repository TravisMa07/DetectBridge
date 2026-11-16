package io.detectbridge.windows;

import static org.junit.jupiter.api.Assertions.*;
import static io.detectbridge.windows.WindowsAdapterTest.*;

import io.detectbridge.detection.Evaluator;
import io.detectbridge.transport.Json;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

class OfflineEvaluationTest {
  @TempDir Path temp;
  Evaluator evaluator() throws Exception { return new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/windows/plan.json"))); }
  JsonNode evaluate(JsonNode event, Evaluator evaluator) {
    byte[] bytes=Json.bytes(event);
    var location=Map.<String,Object>of("cluster_id","offline","topic_id","offline","topic","windows-offline","partition",0,"offset",0,"value_sha256",Json.sha(bytes));
    var selected=evaluator.evaluate(bytes,location); assertEquals(selected,evaluator.evaluateExhaustive(bytes,location)); return selected;
  }
  JsonNode event(String xml, String family, boolean binding) throws Exception {
    var r=raw(xml);return new WindowsAdapter().adapt(r,EvidenceResolver.local(temp),context(r,family,binding)).event();
  }
  void counts(JsonNode result,int matched,int unmatched,int inapplicable,int blocked,int skipped,int error) {
    int[] literal={matched,unmatched,inapplicable,blocked,skipped,error};
    for(int i=0;i<literal.length;i++) assertEquals(literal[i],result.get("counts").get(Evaluator.OUTCOMES.get(i)).asInt(),Evaluator.OUTCOMES.get(i));
  }
  @Test void allSixLiteralOutcomesAcrossOfflineParserOutputs() throws Exception {
    // Image exact match, Image different, Linux logsource, CommandLine different.
    for(String family:List.of("security","sysmon")) {
      var result=evaluate(event(fixture(family),family,true),evaluator()); counts(result,1,2,1,0,0,0);
      assertEquals("71100000-0000-4000-8000-000000000001",result.get("matched").get(0).get("id").asString());
      // Static source mismatch still precedes missing-host quality.
      counts(evaluate(event(fixture(family),family,false),evaluator()),0,0,1,0,3,0);
    }
    // An unrelated bundle does not contain either parser-backed source contract.
    var unrelated=new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/mapped-plan.json")));
    counts(evaluate(event(fixture("security"),"security",true),unrelated),0,0,0,1,0,0);
    // 20 tokens x 65536 source codepoints exceeds the public 1,000,000 tick budget.
    String large=fixture("security").replace("synthetic.exe &quot;α 😀&quot;","x".repeat(65536));
    counts(evaluate(event(large,"security",true),evaluator()),1,1,1,0,0,1);
  }
  @Test void integratedConsumerRetainsAllSixOutcomesAndPreservation() throws Exception {
    var processor = new io.detectbridge.detection.IntegrationOutputs(evaluator());
    for (String family : List.of("security", "sysmon")) {
      var r = raw(fixture(family)); var c = context(r, family, true);
      var input = temp.resolve("integrated-input"); var output = temp.resolve("integrated-output");
      Files.write(input, Json.bytes(Map.of("raw", r, "context", c)));
      assertEquals(1, Offline.runIntegrated(input, output, EvidenceResolver.local(temp), evaluator()));
      var row = Json.read(Files.readAllBytes(output)); var integration = row.get("integration");
      counts(integration.get("tagged"), 1, 2, 1, 0, 0, 0);
      assertEquals(1, integration.get("detections").size()); assertEquals(0, integration.get("diagnostics").size());
      assertEquals(r, row.get("raw")); assertEquals(c, row.get("context"));
      assertEquals(row.get("event"), integration.at("/tagged/event"));
      assertEquals(c.at("/source_contract/sha256"), integration.at("/tagged/attribution/source_contract/sha256"));
      assertEquals(c.at("/mapping_profile/sha256"), integration.at("/tagged/attribution/mapping_profile/sha256"));
      processor.verify(integration, null, c);
      var unrelated = new Evaluator(Files.readAllBytes(ROOT.resolve(".cache/detection/mapped-plan.json")));
      Offline.runIntegrated(input, output, EvidenceResolver.local(temp), unrelated);
      var blocked = Json.read(Files.readAllBytes(output)).get("integration");
      counts(blocked.get("tagged"), 0, 0, 0, 1, 0, 0);
      assertEquals(c.at("/source_contract/sha256"), blocked.at("/tagged/attribution/source_contract/sha256"));
      new io.detectbridge.detection.IntegrationOutputs(unrelated).verify(blocked, null, c);
      var skipped = processor.process(event(fixture(family), family, false), null);
      counts(skipped.get("tagged"), 0, 0, 1, 0, 3, 0);
      assertEquals(1, skipped.get("diagnostics").size()); assertEquals(3, skipped.at("/diagnostics/0/rule_set/count").asInt());
      assertFalse(skipped.at("/tagged/event/detectbridge/quality/diagnostics").isEmpty());
      assertEquals(0, skipped.get("detections").size());
    }
    var large = processor.process(event(fixture("security").replace("synthetic.exe &quot;α 😀&quot;", "x".repeat(65536)), "security", true), null);
    counts(large.get("tagged"), 1, 1, 1, 0, 0, 1);
    assertEquals("evaluation_error", large.at("/diagnostics/0/category").asString());
    var r = raw("<invalid/>"); var c = context(r, "security", true);
    var input = temp.resolve("preservation-input"); var output = temp.resolve("preservation-output");
    Files.write(input, Json.bytes(Map.of("raw", r, "context", c)));
    Offline.runIntegrated(input, output, EvidenceResolver.local(temp), evaluator());
    var row = Json.read(Files.readAllBytes(output)); assertTrue(row.has("preservation")); assertFalse(row.has("integration"));
    byte[] previous = Files.readAllBytes(output);
    assertThrows(java.io.IOException.class, () -> Offline.runIntegrated(input, output, ignored -> { throw new java.io.IOException("unavailable"); }, evaluator()));
    assertArrayEquals(previous, Files.readAllBytes(output));
    ((ObjectNode) r.get("evidence")).put("sha256", "0".repeat(64));
    Files.write(input, Json.bytes(Map.of("raw", r, "context", c)));
    Offline.runIntegrated(input, output, EvidenceResolver.local(temp), evaluator());
    row = Json.read(Files.readAllBytes(output)); assertTrue(row.has("preservation")); assertFalse(row.has("integration"));
  }
  @Test void actualAtomicRunnerPublishesEvaluationAndContext() throws Exception {
    var r=raw(fixture("security"));var c=context(r,"security",true);
    var input=temp.resolve("input");var output=temp.resolve("output");
    Files.write(input,Json.bytes(Map.of("raw",r,"context",c)));
    assertEquals(1,Offline.run(input,output,EvidenceResolver.local(temp),evaluator()));
    var row=Json.read(Files.readAllBytes(output));counts(row.get("evaluation"),1,2,1,0,0,0);
    assertEquals(c,row.get("context"));
    assertEquals("windows-xml/1.0.0",row.at("/event/detectbridge/processing/parser").asString());
    assertEquals("detectbridge-java/2.0.0",row.at("/evaluation/evaluator").asString());
  }
}
