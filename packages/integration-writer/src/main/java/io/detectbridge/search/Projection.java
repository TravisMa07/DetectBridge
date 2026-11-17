package io.detectbridge.search;

import com.networknt.schema.*;
import io.detectbridge.transport.Json;
import io.detectbridge.detection.Contracts;
import io.detectbridge.detection.IntegrationOutputs;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/** P13 derived view. Never resolves evidence or evaluates a rule. */
public final class Projection {
  public static final String INPUT = "detectbridge.integration.input.v1";
  public static final String OUTPUT = "detectbridge.tagged-events.v1";
  public static final String DETECTIONS = "detectbridge.detections.v1";
  public static final String PROCESSING = "detectbridge.processing-diagnostics.v1";
  public static final String FAILURES = "detectbridge.integration.writer-failures.v1";
  public static final String TAGGED = "detectbridge-tagged-events-v1";
  public static final String DETECTION_INDEX = "detectbridge-detections-v1";
  public static final String DIAGNOSTICS = "detectbridge-processing-diagnostics-v1";
  public static final List<String> INDICES = List.of(TAGGED, DETECTION_INDEX, DIAGNOSTICS);
  public static final List<String> TOPICS = List.of(OUTPUT, DETECTIONS, PROCESSING, FAILURES);
  public static final List<String> SOURCE_TOPICS = List.of(INPUT, OUTPUT, DETECTIONS, PROCESSING,
      "detectbridge.integration.manifests.v1", "detectbridge.integration.preservation.v1",
      "detectbridge.integration.quarantine.v1", "detectbridge.integration.receipts.v1", FAILURES);
  private final JsonNode config;
  private final Contracts contracts = new Contracts();
  private final Map<String,Schema> schemas = new HashMap<>();
  public record Location(String cluster_id, String topic_id, String topic, int partition, long offset) {}
  public record Document(String index, String id, Map<String,Object> body) {}
  public static final class Invalid extends RuntimeException {
    public final String category;
    public Invalid(String category) { super(category); this.category=category; }
  }
  public Projection(JsonNode config) {
    this.config=config;
    for(String name:List.of("configuration","projection","failure")) {
      try(var in=Projection.class.getResourceAsStream("/search-writer/v1/"+name+".schema.json")) {
        String text=new String(Objects.requireNonNull(in).readAllBytes(),StandardCharsets.UTF_8);
        JsonNode schema=Json.MAPPER.readTree(text);
        var registry=SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,
            builder->builder.schemas(Map.of(schema.get("$id").asString(),text)));
        schemas.put(name,registry.getSchema(SchemaLocation.of(schema.get("$id").asString())));
      } catch(Exception ex) { throw new IllegalStateException("search_schema_load_failure"); }
    }
  }
  public void require(String kind,JsonNode value) {
    if(!schemas.get(kind).validate(value,c->c.executionConfig(e->e.formatAssertionsEnabled(true))).isEmpty())
      throw new Invalid("schema_invalid");
  }
  public static Object canonical(JsonNode value) { return Contracts.canonical(value); }
  public static String hash(Object value) { return Json.sha(Json.bytes(canonical(Json.MAPPER.valueToTree(value)))); }
  public static ObjectNode semanticEvent(JsonNode event) {
    ObjectNode result=((ObjectNode)event).deepCopy();
    ((ObjectNode)result.get("event")).remove("ingested");
    ((ObjectNode)result.at("/detectbridge/time")).remove(List.of("received","processed"));
    JsonNode context=result.at("/detectbridge/extensions/linux.context/context");
    if(context.isObject()) ((ObjectNode)context).remove("receipt");
    return result;
  }
  public static String contentHash(JsonNode body) {
    ObjectNode copy=((ObjectNode)body).deepCopy();
    copy.remove(List.of("content_sha256","first_input","input_sha256","evidence_source"));
    if(copy.hasNonNull("manifest")) copy.set("manifest",Json.MAPPER.valueToTree(
        Map.of("semantic_sha256",copy.at("/manifest/semantic_sha256"))));
    return hash(copy);
  }
  private static void check(boolean condition,String category) { if(!condition) throw new Invalid(category); }
  private Map<String,Object> sourceLink(String topic) {
    return Map.of("cluster_id",config.get("kafka_cluster_id").asString(),"topic",topic,
        "topic_id",config.at("/source_topics/"+topic+"/id").asString());
  }
  private static Object versions(JsonNode a) {
    Map<String,Object> v=new TreeMap<>();
    for(String key:List.of("compiler","evaluator","selector","mapping_version","bundle_sha256","context_sha256"))
      if(a.hasNonNull(key)) v.put(key,canonical(a.get(key)));
    for(String key:List.of("parser","normalizer","mapping")) v.put(key,a.at("/processing/"+key).asString());
    v.put("source_contract",a.at("/source_contract/id").asString()+"/"+a.at("/source_contract/version").asString());
    if(a.at("/source_contract/sha256").isString()) v.put("source_sha256",a.at("/source_contract/sha256").asString());
    if(a.hasNonNull("mapping_profile")) {
      v.put("mapping_profile",a.at("/mapping_profile/id").asString()+"/"+a.at("/mapping_profile/version").asString());
      v.put("mapping_sha256",a.at("/mapping_profile/sha256").asString());
    }
    v.put("enrichment",a.at("/enrichment/id").asString()+"/"+a.at("/enrichment/version").asString());
    v.put("enrichment_sha256",a.at("/enrichment/sha256").asString());
    return v;
  }
  public Document project(String topic,byte[] key,byte[] value,Location location) {
    JsonNode node;
    try {
      check(value!=null && value.length<=2*Json.MAX_VALUE,"input_limit");
      node=Json.MAPPER.readTree(value);
      io.detectbridge.detection.Normalized.unicode(node);
    } catch(Exception ex) { throw new Invalid("invalid_json"); }
    Map<String,Object> body=new TreeMap<>();
    body.put("contract_version","1.0.0"); body.put("mode","p13-search/1.0.0");
    body.put("pipeline_id",config.get("pipeline_id").asString());
    body.put("input_sha256",Json.sha(value)); body.put("first_input",location);
    String id,index;
    if(topic.equals(FAILURES)) {
      require("failure",node); id=node.get("failure_id").asString();
      check(id.equals(failureId(node.get("input"))),"failure_identity_mismatch");
      var input=node.get("input");
      check(config.get("kafka_cluster_id").equals(input.get("cluster_id"))
          && TOPICS.contains(input.get("topic").asString()) && !input.get("topic").asString().equals(FAILURES)
          && config.at("/source_topics/"+input.get("topic").asString()+"/id").equals(input.get("topic_id")),"failure_source_mismatch");
      body.put("kind","writer_failure"); body.put("diagnostic",canonical(node));
      body.put("category",node.at("/diagnostic/category").asString()); index=DIAGNOSTICS;
    } else {
      String kind=topic.equals(OUTPUT)?"tagged-event":topic.equals(DETECTIONS)?"detection":topic.equals(PROCESSING)?"diagnostic":"";
      check(!kind.isEmpty() && node.path("version").asString().equals("1.1.0"),"unsupported_search_input");
      try { contracts.require("integration",kind,node); } catch(Exception ex) { throw new Invalid("integration_schema_invalid"); }
      JsonNode a=node.get("attribution");
      check(a.path("pipeline").asString().equals(IntegrationOutputs.RUNTIME_PIPELINE)
          && a.get("bundle_sha256").equals(config.get("evaluation_bundle_sha256")),"evaluation_binding_mismatch");
      body.put("attribution",canonical(a)); body.put("versions",versions(a)); body.put("source",canonical(a.get("source")));
      String processing=node.get("processing_id").asString();
      body.put("processing_id",processing);
      if(topic.equals(OUTPUT)) {
        JsonNode event=node.get("event"),db=event.get("detectbridge");
        String eventHash=hash(semanticEvent(event));
        check(db.get("source").equals(a.get("source"))
            && db.get("processing").equals(a.get("processing"))
            && db.at("/source_contract/id").equals(a.at("/source_contract/id"))
            && db.at("/source_contract/version").equals(a.at("/source_contract/version")),"event_attribution_mismatch");
        Object manifest=node.get("manifest").isNull()?null:Map.of("semantic_sha256",node.at("/manifest/semantic_sha256"));
        check(processing.equals(IntegrationOutputs.identity("detectbridge.p13.processing/1",
            IntegrationOutputs.RUNTIME_PIPELINE,db.get("run_id").asString(),event.at("/event/id").asString(),eventHash,a,manifest)),"processing_identity_mismatch");
        check(node.at("/counts/matched").asInt()==node.get("matches").size(),"match_count_mismatch");
        Set<String> matched=new HashSet<>();
        for(var match:node.get("matches")) check(matched.add(match.get("id").asString())
            && match.get("detection_id").asString().equals(IntegrationOutputs.identity("detectbridge.p13.detection/1",processing,match.get("id"),match.get("revision"))),"match_identity_mismatch");
        body.put("kind","tagged"); id=processing; index=TAGGED;
        body.put("event_id",event.at("/event/id").asString()); body.put("run_id",db.get("run_id").asString());
        body.put("semantic_event_sha256",eventHash);
        for(String field:List.of("host","process","user")) if(event.has(field)) body.put(field,canonical(event.get(field)));
        ObjectNode ecs=((ObjectNode)event.get("event")).deepCopy(); ecs.remove("ingested"); body.put("event",canonical(ecs));
        ObjectNode time=((ObjectNode)db.get("time")).deepCopy(); time.remove(List.of("received","processed")); body.put("time",canonical(time));
        String timestamp=event.get("@timestamp").asString(); body.put("original_timestamp",timestamp);
        try { Instant instant=Instant.parse(timestamp); long nanos=Math.addExact(Math.multiplyExact(instant.getEpochSecond(),1000000000L),instant.getNano());
          if(nanos<0) throw new ArithmeticException(); body.put("@timestamp",timestamp);
        } catch(Exception ex) { body.put("time_projection_reason","outside_nanos_range_or_precision"); }
        body.put("quality",canonical(db.get("quality"))); body.put("eligibility",db.at("/quality/eligibility").asString());
        Set<String> findings=new LinkedHashSet<>(); for(var diagnostic:db.at("/quality/diagnostics")) findings.add(diagnostic.get("code").asString()); var sourceFindings=db.at("/extensions/linux.context/findings");
        if(sourceFindings.isArray()) for(var finding:sourceFindings) findings.add(finding.asString());
        body.put("source_findings",new ArrayList<>(findings));
        for(String field:List.of("counts","matches","tags")) body.put(field,canonical(node.get(field)));
        List<Object> evidence=new ArrayList<>(); List<String> records=new ArrayList<>(),hashes=new ArrayList<>();
        for(var member:db.get("evidence")) {
          Map<String,Object> item=new TreeMap<>(); item.put("record_id",member.get("record_id").asString());
          var e=member.get("evidence"); for(String f:List.of("sha256","encoding","media_type","reference")) if(e.has(f)) item.put(f,canonical(e.get(f)));
          item.put("inline_present",e.has("inline")); evidence.add(item); records.add(member.get("record_id").asString()); hashes.add(e.get("sha256").asString());
        }
        body.put("evidence",evidence); body.put("record_ids",records); body.put("evidence_hashes",hashes); body.put("evidence_source",sourceLink(INPUT));
      } else {
        body.put("event_id",node.get("event_id").asString()); body.put("run_id",node.get("run_id").asString());
        if(topic.equals(DETECTIONS)) {
          var rule=node.get("rule"); id=node.get("detection_id").asString(); index=DETECTION_INDEX; body.put("kind","detection");
          check(id.equals(IntegrationOutputs.identity("detectbridge.p13.detection/1",processing,rule.get("id"),rule.get("revision"))),"detection_identity_mismatch");
          body.put("rule",canonical(rule)); body.put("rule_id",rule.get("id").asString()); body.put("rule_revision",rule.get("revision").asString());
        } else {
          id=node.get("diagnostic_id").asString(); index=DIAGNOSTICS; body.put("kind","processing");
          check(id.equals(IntegrationOutputs.identity("detectbridge.p13.diagnostic/1",processing,node.get("category"),node.at("/rule_set/sha256"))),"diagnostic_identity_mismatch");
          body.put("category",node.get("category").asString()); body.put("rule_set",canonical(node.get("rule_set")));
          body.put("rule_set_sha256",node.at("/rule_set/sha256").asString()); body.put("rule_count",node.at("/rule_set/count").asInt());
        }
      }
      if(node.hasNonNull("manifest")) { var ref=(ObjectNode)node.get("manifest").deepCopy();
        ref.set("location",Json.MAPPER.valueToTree(sourceLink("detectbridge.integration.manifests.v1"))); body.put("manifest",canonical(ref)); }
    }
    check(key!=null && Arrays.equals(key,id.getBytes(StandardCharsets.UTF_8)),"search_key_mismatch");
    body.put("content_sha256",contentHash(Json.MAPPER.valueToTree(body))); require("projection",Json.MAPPER.valueToTree(body));
    return new Document(index,id,body);
  }
  public static String failureId(JsonNode input) { return Json.identity(List.of("p13-search-writer:1.0.0",
      input.get("cluster_id").asString(),input.get("topic_id").asString(),input.get("partition").asString(),input.get("offset").asString())); }
  public Map<String,Object> failure(Location location,byte[] value,String reason) {
    Map<String,Object> result=Map.of("contract_version","1.0.0","failure_id",failureId(Json.MAPPER.valueToTree(location)),"input",location,
        "value_is_null",value==null,"value_size",value==null?0:value.length,"value_sha256",Json.sha(value==null?new byte[0]:value),
        "diagnostic",Map.of("category",reason,"pointer","")); require("failure",Json.MAPPER.valueToTree(result)); return result;
  }
  private static Map<String,Object> keyword() { return Map.of("type","keyword","ignore_above",4096); }
  private static Map<String,Object> object(Map<String,Object> properties) { return Map.of("type","object","dynamic","strict","properties",properties); }
  public static Map<String,Object> mapping() {
    Map<String,Object> fields=new TreeMap<>();
    for(String key:List.of("contract_version","mode","kind","pipeline_id","input_sha256","content_sha256","processing_id","event_id","run_id","semantic_event_sha256","original_timestamp","time_projection_reason","eligibility","category","rule_id","rule_revision","rule_title","rule_tags","tags","record_ids","evidence_hashes","source_findings","rule_set_sha256")) fields.put(key,keyword());
    fields.put("@timestamp",Map.of("type","date_nanos","format","strict_date_optional_time_nanos")); fields.put("rule_count",Map.of("type","long"));
    for(String key:List.of("attribution","time","quality","evidence","manifest","evidence_source","rule","rule_set","diagnostic")) fields.put(key,Map.of("type","object","enabled",false));
    fields.put("source",object(Map.of("namespace",keyword(),"instance",keyword())));
    Map<String,Object> versions=new TreeMap<>(); for(String key:List.of("compiler","evaluator","selector","mapping_version","bundle_sha256","context_sha256","parser","normalizer","mapping","source_contract","source_sha256","mapping_profile","mapping_sha256","enrichment","enrichment_sha256")) versions.put(key,keyword()); fields.put("versions",object(versions));
    Map<String,Object> counts=new TreeMap<>(); for(String outcome:io.detectbridge.detection.Evaluator.OUTCOMES) counts.put(outcome,Map.of("type","long")); fields.put("counts",object(counts));
    fields.put("matches",Map.of("type","nested","dynamic","strict","properties",Map.of("id",keyword(),"revision",keyword(),"detection_id",keyword())));
    Map<String,Object> event=new TreeMap<>(); for(String key:List.of("id","kind","category","type","code","action","outcome","created","provider","dataset")) event.put(key,keyword()); fields.put("event",object(event));
    fields.put("host",object(Map.of("id",keyword(),"name",keyword(),"hostname",keyword(),"ip",Map.of("type","ip"))));
    fields.put("user",object(Map.of("id",keyword(),"name",keyword(),"domain",keyword())));
    Map<String,Object> process=new TreeMap<>(); for(String key:List.of("entity_id","name","executable","command_line","args","working_directory")) process.put(key,keyword()); process.put("pid",Map.of("type","long")); var parent=new TreeMap<>(process); process.put("parent",object(parent)); fields.put("process",object(process));
    fields.put("first_input",object(Map.of("cluster_id",keyword(),"topic_id",keyword(),"topic",keyword(),"partition",Map.of("type","integer"),"offset",Map.of("type","long"))));
    return fields;
  }
}
