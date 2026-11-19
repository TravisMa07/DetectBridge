package io.detectbridge.archive;

import static io.detectbridge.archive.Format.*;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.*;

/** Dry, bounded dependency analysis. The caller owns the registered catalog lock and archive lease. */
final class ManagedPlanner {
  private ManagedPlanner() {}
  static final String LINK="detectbridge.archive.link/1";
  static String token(String value) { return hash(List.of(LINK,value)); }
  static void keys(JsonNode value,Set<String> expected,String category)throws IOException {
    check(value!=null&&value.isObject()&&value.size()==expected.size(),category);
    for(var e:value.properties())check(expected.contains(e.getKey()),category);
  }
  static long nonnegative(JsonNode value,String category)throws IOException {
    check(value!=null&&value.isIntegralNumber()&&value.canConvertToLong()&&value.asLong()>=0,category);return value.asLong();
  }
  static final class Graph {
    final Set<String> identities=new TreeSet<>();
    final Set<String> fingerprints=new TreeSet<>();
    boolean unknown;
    boolean recognized;
  }
  static final Set<String> IDENTITIES=Set.of("run_id","record_id","event_id","manifest_id","original_manifest_id","processing_id","detection_id","diagnostic_id","preservation_id","control_id");
  static final Set<String> NON_EVIDENCE=Set.of("host_id","boot_id","topic_id","cluster_id","rule_id","policy_id","plan_id","selector_id","parser_id","schema_id","mapping_id","enrichment_id","adapter_id","source_id");
  static void links(JsonNode value,String path,Graph graph,int depth)throws IOException {
    check(depth<=64,"managed_graph_depth");
    if(graph.recognized&&ManagedGraph.observational(path))return;
    if(value.isArray()){for(JsonNode child:value)links(child,path+"/*",graph,depth+1);return;}
    if(!value.isObject())return;
    if(path.endsWith("/input")&&value.has("offset")) {
      if(value.path("cluster_id").isTextual()&&value.path("topic_id").isTextual()&&value.path("partition").isIntegralNumber()&&value.get("partition").asLong()==0&&value.get("offset").isIntegralNumber()&&value.get("offset").canConvertToLong()&&value.get("offset").asLong()>=0)
        graph.identities.add(token(Store.wireId(value.get("cluster_id").asString(),value.get("topic_id").asString(),value.get("offset").asLong())));
      else graph.unknown=true;
    }
    for(var e:value.properties()) {
      String key=e.getKey(),childPath=path+"/"+key;JsonNode child=e.getValue();
      boolean identity=IDENTITIES.contains(key)||key.equals("id")&&(path.isEmpty()||path.equals("/diagnostic")||path.endsWith("/event"));
      if(identity) {
        if(child.isTextual()&&!child.asString().isEmpty())graph.identities.add(token(child.asString()));
        else if(!child.isNull())graph.unknown=true;
      } else if(key.endsWith("_id")&&!NON_EVIDENCE.contains(key))graph.unknown=true;
      if(Set.of("references","links","dependencies").contains(key))graph.unknown=true;
      links(child,childPath,graph,depth+1);
    }
  }
  static Graph graph(JsonNode wire)throws IOException {
    Graph graph=new Graph();graph.identities.add(token(wire.get("id").asString()));
    String category=wire.get("category").asString(),topic=wire.get("topic").asString();
    JsonNode doc=Main.parsed(decode(wire.get("value")));
    if(doc==null||!doc.isObject()){graph.unknown=true;return graph;}
    // The legacy conflict scan compares every INPUT raw/context object, even a rejected
    // source. A derived-topic document is never a prior input occurrence.
    if(topic.equals(Main.INPUT)&&doc.path("raw").isObject()&&doc.path("context").isObject()) {
      String identity=Main.sourceIdentity(doc),content;
      try{content=Main.fingerprint(doc);}catch(IllegalArgumentException invalid){content=hash(List.of("detectbridge.archive.invalid-fingerprint/1",identity));}
      graph.fingerprints.add(hash(identity)+"/"+content);
    }
    boolean known=ManagedGraph.known(topic,doc);
    if(topic.equals(Main.INPUT))known&=Set.of("run_end","source_boundary").contains(doc.path("kind").asString(""))?category.equals("control"):category.equals("source");
    else known&=category.equals("derived");
    graph.recognized=known;graph.unknown=!known;
    links(doc,"",graph,0);return graph;
  }
  static final class Budget {
    long rows,tokens;
    final long rowLimit,tokenLimit;
    Budget(ManagedStore store){rowLimit=store.registration.at("/limits/scan_rows").asLong();tokenLimit=store.registration.at("/limits/identity_tokens").asLong();}
    void add(Graph graph)throws IOException {check(++rows<=rowLimit,"managed_scan_budget");tokens=Math.addExact(tokens,graph.identities.size());check(tokens<=tokenLimit,"managed_identity_budget");}
  }
  static JsonNode plan(ManagedStore store,JsonNode request,JsonNode catalog)throws IOException {
    keys(request,Set.of("operation_id","cutoff_ms","targets","reason"),"managed_plan_request");integers(request);
    check(request.path("operation_id").isTextual()&&request.get("operation_id").asString().matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),"managed_operation_id");
    long cutoff=nonnegative(request.get("cutoff_ms"),"managed_cutoff");
    check(request.path("reason").isTextual()&&!request.get("reason").asString().isEmpty()&&request.get("reason").asString().codePointCount(0,request.get("reason").asString().length())<=256,"managed_reason");
    JsonNode requested=request.get("targets");check(requested.isArray()&&!requested.isEmpty()&&requested.size()<=9,"managed_targets");
    Map<String,Long> targets=new TreeMap<>();
    for(JsonNode target:requested) {
      keys(target,Set.of("topic","next"),"managed_target");String name=target.path("topic").asString("");store.topic(name);
      long next=nonnegative(target.get("next"),"managed_target");check(targets.put(name,next)==null&&next>store.floors.get(name).next()&&next<=store.prefix(name).next(),"managed_target");
    }
    validateCatalog(store,catalog);
    ObjectNode plan=JSON.createObjectNode();plan.put("version","1.0.0");plan.put("managed_id",store.managed);plan.put("archive_binding_sha256",store.binding);
    plan.set("operation_id",request.get("operation_id"));plan.put("kind","segments");plan.put("cutoff_ms",cutoff);plan.set("reason",request.get("reason"));
    if(store.retirementHash==null)plan.putNull("previous_retirement_sha256");else plan.put("previous_retirement_sha256",store.retirementHash);
    plan.put("holds_sha256",hash(store.holds));plan.put("catalog_sha256",hash(catalog));ArrayNode observed=plan.putArray("observed"),selected=plan.putArray("candidates"),targetArray=plan.putArray("targets");plan.putArray("imports");
    targets.forEach((name,next)->targetArray.addObject().put("topic",name).put("next",next));
    Set<String> selectedIds=new TreeSet<>(),retainedIds=new TreeSet<>(),newFingerprints=new TreeSet<>();
    for(var e:store.fingerprints.entrySet())for(String content:e.getValue())newFingerprints.add(e.getKey()+"/"+content);
    Budget budget=new Budget(store);long selectedRows=0;boolean unknown=false;
    for(String name:new TreeSet<>(store.floors.keySet())) {
      ManagedStore.Prefix floor=store.floors.get(name),head=store.prefix(name);JsonNode topic=store.topic(name);
      ObjectNode observation=observed.addObject();observation.put("topic",name).put("floor",floor.next()).put("next",head.next());nullable(observation,"floor_sha256",floor.previous());nullable(observation,"head_sha256",head.previous());
      ManagedStore.Prefix previous=floor;long target=targets.getOrDefault(name,floor.next());
      while(previous.next()<head.next()) {
        Path directory=store.partition(topic).resolve(Long.toString(previous.next()));JsonNode meta=store.segment(directory,topic,previous);
        boolean candidate=previous.next()<target;check(!candidate||meta.get("next").asLong()<=target,"managed_target_not_boundary");
        Graph segmentGraph=new Graph();List<JsonNode> rows=store.segmentRows(directory,meta,topic);
        for(JsonNode row:rows) {
          Graph graph=graph(row);budget.add(graph);unknown|=graph.unknown;
          if(candidate) {
            long timestamp=row.get("timestamp").asLong();check(timestamp>=0&&timestamp<=cutoff,"managed_cutoff_timestamp");selectedRows++;
            segmentGraph.identities.addAll(graph.identities);segmentGraph.fingerprints.addAll(graph.fingerprints);segmentGraph.unknown|=graph.unknown;
            selectedIds.addAll(graph.identities);newFingerprints.addAll(graph.fingerprints);
          } else retainedIds.addAll(graph.identities);
        }
        if(candidate) {
          check(selected.size()<store.registration.at("/limits/plan_segments").asLong(),"managed_plan_segment_budget");
          ObjectNode item=selected.addObject();item.put("topic",name);item.set("segment",meta);item.put("segment_sha256",hash(meta));item.put("unknown_graph",segmentGraph.unknown);
          ArrayNode ids=item.putArray("identities");segmentGraph.identities.forEach(ids::add);ArrayNode fps=item.putArray("fingerprints");
          for(String fp:segmentGraph.fingerprints){String[] parts=fp.split("/",2);fps.addObject().put("identity_sha256",parts[0]).put("content_sha256",parts[1]);}
        }
        previous=new ManagedStore.Prefix(meta.get("next").asLong(),hash(meta));
      }
    }
    check(!selected.isEmpty(),"managed_empty_retirement");check(newFingerprints.size()<=store.registration.at("/limits/source_fingerprints").asLong(),"managed_fingerprint_budget");
    check(Collections.disjoint(selectedIds,retainedIds),"managed_retained_identity_blocker");
    holds(store,plan,selectedIds);pins(store,plan,catalog);
    check(!unknown||selectedRows==budget.rows&&store.holds.get("holds").isEmpty()&&catalog.get("pins").isEmpty(),"managed_unknown_graph_blocker");
    ManagedFormat.require("plan",plan);check(ndjson(plan).length<=store.registration.at("/limits/metadata_bytes").asLong(),"managed_metadata_limit");return plan;
  }
  static void nullable(ObjectNode node,String key,String value){if(value==null)node.putNull(key);else node.put(key,value);}
  static void validateCatalog(ManagedStore store,JsonNode catalog)throws IOException {
    keys(catalog,Set.of("version","destination","pins"),"managed_catalog_snapshot");
    check(catalog.path("version").asString("").equals("1.0.0")&&catalog.path("destination").equals(store.registration.get("catalog_destination"))&&catalog.path("pins").isArray()&&bytes(catalog).length<=16*MIB,"managed_catalog_snapshot");
    String previous="";
    for(JsonNode pin:catalog.get("pins")) {
      keys(pin,Set.of("selection_sha256","selection"),"managed_catalog_pin");JsonNode selection=pin.get("selection");String sha=pin.path("selection_sha256").asString("");
      check(sha.matches("[a-f0-9]{64}")&&sha.compareTo(previous)>0&&hash(selection).equals(sha)&&selection.path("archive_binding_sha256").asString("").equals(store.binding),"managed_catalog_pin");previous=sha;
    }
  }
  static void holds(ManagedStore store,JsonNode plan,Set<String> selectedIds)throws IOException {
    for(JsonNode hold:store.holds.get("holds")) {
      String scope=hold.get("scope").asString();boolean blocked=scope.equals("all");
      if(scope.equals("run")) {check(hold.get("subject").isTextual(),"managed_hold_scope");blocked=selectedIds.contains(token(hold.get("subject").asString()));}
      if(scope.equals("range")) {
        check(hold.get("topic").isTextual(),"managed_hold_scope");store.topic(hold.get("topic").asString());long first=nonnegative(hold.get("first"),"managed_hold_scope"),next=nonnegative(hold.get("next"),"managed_hold_scope");check(next>first,"managed_hold_scope");
        for(JsonNode candidate:plan.get("candidates"))if(candidate.get("topic").equals(hold.get("topic")))blocked|=candidate.at("/segment/first").asLong()<next&&candidate.at("/segment/next").asLong()>first;
      }
      if(scope.equals("object")) {
        check(hold.get("subject").isTextual(),"managed_hold_scope");
        for(JsonNode candidate:plan.get("candidates"))blocked|=Store.strings(candidate.at("/segment/dependencies")).contains(hold.get("subject").asString());
      }
      check(!blocked,"managed_hold_blocker");
    }
  }
  static void pins(ManagedStore store,JsonNode plan,JsonNode catalog)throws IOException {
    for(JsonNode pin:catalog.get("pins"))references(store,plan,pin.get("selection"),0);
  }
  static void references(ManagedStore store,JsonNode plan,JsonNode value,int depth)throws IOException {
    check(depth<=64,"managed_catalog_graph");
    if(value.isObject()) {
      if(value.has("topic")||value.has("offset")) {
        check(value.path("topic").isTextual()&&value.has("offset"),"managed_catalog_reference");String topic=value.get("topic").asString();store.topic(topic);long offset=nonnegative(value.get("offset"),"managed_catalog_reference");
        for(JsonNode candidate:plan.get("candidates"))check(!candidate.get("topic").asString().equals(topic)||offset<candidate.at("/segment/first").asLong()||offset>=candidate.at("/segment/next").asLong(),"managed_pin_blocker");
      }
      for(JsonNode child:value)references(store,plan,child,depth+1);
    } else if(value.isArray())for(JsonNode child:value)references(store,plan,child,depth+1);
  }
}
