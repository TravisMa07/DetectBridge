package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import com.networknt.schema.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Recognition of the pinned, closed processing graphs; unfamiliar native shapes remain unknown. */
final class ManagedGraph {
  static final List<String> RESOURCES=List.of(
      "contracts/v1/common.schema.json", "contracts/v1/raw-record.schema.json", "contracts/v1/normalized-event.schema.json",
      "contracts/detection/v2/candidate-provenance.schema.json",
      "contracts/integration/v1.1/common.schema.json", "contracts/integration/v1.1/tagged-event.schema.json",
      "contracts/integration/v1.1/detection.schema.json", "contracts/integration/v1.1/diagnostic.schema.json",
      "contracts/integration-runtime/v1/integration-input.schema.json", "contracts/integration-runtime/v1/integration-receipt.schema.json",
      "contracts/integration-runtime/v1/integration-preservation.schema.json",
      "packages/linux-adapters/contracts/context.schema.json", "packages/linux-adapters/contracts/context-extension.schema.json",
      "packages/linux-adapters/contracts/manifest.schema.json", "packages/linux-adapters/contracts/preservation.schema.json");
  static final Map<String,String> TOPICS=Map.of(
      "detectbridge.integration.input.v1","urn:detectbridge:integration-runtime:1.0.0:input",
      "detectbridge.tagged-events.v1","urn:detectbridge:integration:1.1.0:tagged-event",
      "detectbridge.detections.v1","urn:detectbridge:integration:1.1.0:detection",
      "detectbridge.processing-diagnostics.v1","urn:detectbridge:integration:1.1.0:diagnostic",
      "detectbridge.integration.receipts.v1","urn:detectbridge:integration-runtime:1.0.0:receipt",
      "detectbridge.integration.preservation.v1","urn:detectbridge:integration-runtime:1.0.0:preservation",
      "detectbridge.integration.manifests.v1","urn:detectbridge:linux:1.0.0:manifest");
  static final Map<String,String> DOCUMENTS=documents();
  private static final SchemaRegistry REGISTRY=registry(DOCUMENTS);
  static Map<String,String> documents() {
    Map<String,String> documents=new TreeMap<>();
    for(String path:RESOURCES)try(var stream=ManagedGraph.class.getResourceAsStream("/archive-graph/"+path)) {
      String text=new String(Objects.requireNonNull(stream).readAllBytes(),StandardCharsets.UTF_8);JsonNode schema=JSON.readTree(text);
      String id=schema.path("$id").asString("");check(id.startsWith("urn:detectbridge:")&&documents.put(id,text)==null,"managed_graph_schema_id");
    }catch(Exception failure){throw new ExceptionInInitializerError(failure);}
    return Collections.unmodifiableMap(documents);
  }
  static void references(JsonNode node,String base,Map<String,JsonNode> documents,int depth)throws IOException {
    check(depth<=128,"managed_graph_schema_depth");
    if(node.isObject()) {
      check(!node.has("$dynamicRef")&&!node.has("$recursiveRef"),"managed_graph_schema_reference");
      if(node.has("$ref")) {
        check(node.get("$ref").isTextual(),"managed_graph_schema_reference");String[] parts=node.get("$ref").asString().split("#",-1);check(parts.length<=2,"managed_graph_schema_reference");
        String target=parts[0].isEmpty()?base:parts[0];check(documents.containsKey(target),"managed_graph_schema_reference");
        if(parts.length==2&&!parts[1].isEmpty()){check(parts[1].startsWith("/")&&!documents.get(target).at(parts[1]).isMissingNode(),"managed_graph_schema_reference");}
      }
      for(JsonNode child:node)references(child,base,documents,depth+1);
    }else if(node.isArray())for(JsonNode child:node)references(child,base,documents,depth+1);
  }
  static SchemaRegistry registry(Map<String,String> texts) {
    try {
      check(texts.keySet().equals(DOCUMENTS.keySet()),"managed_graph_schema_id");Map<String,JsonNode> documents=new TreeMap<>();
      for(var entry:texts.entrySet()){JsonNode schema=JSON.readTree(entry.getValue());check(schema.path("$id").asString("").equals(entry.getKey())&&schema.path("$schema").asString("").equals("https://json-schema.org/draft/2020-12/schema"),"managed_graph_schema_id");documents.put(entry.getKey(),schema);}
      for(var entry:documents.entrySet())references(entry.getValue(),entry.getKey(),documents,0);
      // Replace, rather than supplement, all default resource loaders. No URI can
      // fall through to HTTP, filesystem, classpath or another registered profile.
      return SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,b->b.resourceLoaders(loaders->loaders.values(values->{values.clear();values.add(iri->{String text=texts.get(iri.toString());if(text==null)throw new IllegalStateException("managed_graph_unregistered_resource");return ()->new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8));});})));
    }catch(IOException failure){throw new IllegalArgumentException("managed_graph_schema_invalid",failure);}
  }
  static boolean valid(String id,JsonNode value){return REGISTRY.getSchema(SchemaLocation.of(id)).validate(value,c->c.executionConfig(config->config.formatAssertionsEnabled(true))).isEmpty();}
  static boolean known(String topic,JsonNode doc) {
    String schema=TOPICS.get(topic);if(schema==null||doc==null||!doc.isObject())return false;
    try{integers(doc);}catch(IOException unsupportedNumber){return false;}
    if(!valid(schema,doc))return false;
    if(topic.equals("detectbridge.integration.input.v1")) {
      // The pinned Windows branch leaves context untyped. Do not infer a closed graph.
      return !doc.path("kind").asString("").equals("windows_record");
    }
    if(topic.equals("detectbridge.integration.preservation.v1")) {
      // Linux native diagnostics are closed and pinned; Windows native diagnostics
      // remain open in this accepted contract and therefore conservatively unknown.
      return doc.path("adapter").asString("").equals("linux")&&valid("urn:detectbridge:linux:1.0.0:preservation",doc.get("diagnostic"));
    }
    if(topic.equals("detectbridge.tagged-events.v1")) {
      JsonNode extensions=doc.at("/event/detectbridge/extensions");
      if(!extensions.isMissingNode()&&!extensions.isEmpty()) {
        if(!extensions.isObject()||extensions.size()!=1||!extensions.has("linux.context"))return false;
        if(!valid("urn:detectbridge:linux:1.0.0:context-extension",extensions.get("linux.context")))return false;
      }
    }
    return true;
  }
  static boolean observational(String path){return path.equals("/event/source_fields");}
}
