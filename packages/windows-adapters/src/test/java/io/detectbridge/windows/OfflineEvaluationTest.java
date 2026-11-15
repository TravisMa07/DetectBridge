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
