package io.detectbridge.archive;

import com.networknt.schema.*;
import io.detectbridge.transport.Json;
import java.io.*;
import java.nio.*;
import java.nio.charset.*;
import java.util.*;
import java.util.zip.*;
import tools.jackson.core.*;
import tools.jackson.core.json.JsonFactory;
import tools.jackson.databind.*;
import tools.jackson.databind.json.JsonMapper;

/** Archive-only closed wire/metadata formats. Never reserializes original evidence. */
public final class Format {
  public static final int MIB=1048576, ROW=4*MIB, SEGMENT=16*MIB, OBJECT=32*MIB;
  public static final String CODEC="gzip-ndjson/1.0.0";
  static final JsonMapper JSON=JsonMapper.builder(JsonFactory.builder()
      .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
      .streamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(64)
          .maxStringLength(ROW).maxNumberLength(128).build()).build())
      .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
  private static final Map<String,Schema> SCHEMAS=new HashMap<>();
  static {
    for(String name:List.of("configuration","wire","object","chunk","segment")) {
      try(var in=Format.class.getResourceAsStream("/archive/v1/"+name+".schema.json")) {
        String text=new String(Objects.requireNonNull(in).readAllBytes(),StandardCharsets.UTF_8);
        JsonNode schema=JSON.readTree(text);noRefs(schema);
        var r=SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12,
            b->b.schemas(Map.of(schema.get("$id").asString(),text)));
        SCHEMAS.put(name,r.getSchema(SchemaLocation.of(schema.get("$id").asString())));
      } catch(Exception e) { throw new ExceptionInInitializerError("archive_schema_load"); }
    }
  }
  static void noRefs(JsonNode n) {
    if(n.isObject())for(var e:n.properties()) {if(Set.of("$ref","$dynamicRef").contains(e.getKey()))throw new IllegalArgumentException("nonlocal_schema");noRefs(e.getValue());}
    else if(n.isArray())for(JsonNode v:n)noRefs(v);
  }
  public static final class Failure extends IOException {
    public final String category;
    public Failure(String category) { super(category);this.category=category; }
  }
  public static void check(boolean valid,String category) throws Failure { if(!valid)throw new Failure(category); }
  public static JsonNode read(byte[] bytes,int limit) throws IOException {
    check(bytes.length<=limit,"json_limit");
    try {
      StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes));
      JsonNode n=JSON.readTree(bytes);check(n!=null,"json_invalid");unicode(n);return n;
    } catch(Failure e){throw e;}catch(Exception e){throw new Failure("json_invalid");}
  }
  static void unicode(JsonNode n) throws IOException {
    if(n.isTextual()) {
      String s=n.asString();for(int i=0;i<s.length();i++)if(Character.isSurrogate(s.charAt(i))) {
        check(Character.isHighSurrogate(s.charAt(i))&&i+1<s.length()&&Character.isLowSurrogate(s.charAt(++i)),"unicode_invalid");
      }
    } else if(n.isObject()) {
      for(var e:n.properties()) { unicode(JSON.valueToTree(e.getKey()));unicode(e.getValue()); }
    } else if(n.isArray()) for(JsonNode v:n)unicode(v);
  }
  public static void require(String kind,JsonNode n) throws IOException {
    integers(n);check(SCHEMAS.get(kind).validate(n,c->c.executionConfig(e->e.formatAssertionsEnabled(true))).isEmpty(),"schema_"+kind);
  }
  static void integers(JsonNode n) throws IOException {
    if(n.isNumber())check(n.isIntegralNumber()&&n.canConvertToLong(),"integer_invalid");
    else if(n.isContainer())for(JsonNode v:n)integers(v);
  }
  public static Object canonical(JsonNode n) {
    if(n.isObject()){var m=new TreeMap<String,Object>();n.properties().forEach(e->m.put(e.getKey(),canonical(e.getValue())));return m;}
    if(n.isArray()){var a=new ArrayList<Object>();n.forEach(v->a.add(canonical(v)));return a;}
    if(n.isNull())return null;
    if(n.isTextual())return n.asString();
    if(n.isBoolean())return n.asBoolean();
    if(n.isIntegralNumber())return n.bigIntegerValue();
    throw new IllegalArgumentException("canonical_number_invalid");
  }
  public static byte[] bytes(Object value) {return Json.bytes(canonical(JSON.valueToTree(value)));}
  public static String hash(Object value){return Json.sha(bytes(value));}
  public static byte[] ndjson(Object value){byte[] b=bytes(value);byte[] line=Arrays.copyOf(b,b.length+1);line[line.length-1]=10;return line;}
  public static String b64(byte[] b){return b==null?null:Base64.getEncoder().encodeToString(b);}
  public static byte[] decode(JsonNode n) throws IOException {
    if(n.isNull())return null;
    try {byte[] b=Base64.getDecoder().decode(n.asString());check(Base64.getEncoder().encodeToString(b).equals(n.asString()),"base64_invalid");return b;}
    catch(IllegalArgumentException e){throw new Failure("base64_invalid");}
  }
  /** Fixed single-member RFC1952 frame; level six, mtime zero, no filename/comment. */
  static byte[] compress(byte[] raw) throws IOException {
    var out=new ByteArrayOutputStream();out.write(new byte[]{31,(byte)139,8,0,0,0,0,0,0,(byte)255});
    Deflater d=new Deflater(6,true);
    try {d.setInput(raw);d.finish();byte[] b=new byte[8192];while(!d.finished())out.write(b,0,d.deflate(b));}finally{d.end();}
    CRC32 crc=new CRC32();crc.update(raw);ByteBuffer tail=ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putInt((int)crc.getValue()).putInt(raw.length);
    out.write(tail.array());return out.toByteArray();
  }
  static byte[] decompress(byte[] zipped,int limit) throws IOException {
    check(zipped.length>=18&&Arrays.equals(Arrays.copyOf(zipped,10),new byte[]{31,(byte)139,8,0,0,0,0,0,0,(byte)255}),"gzip_header");
    Inflater i=new Inflater(true);var out=new ByteArrayOutputStream();
    try {
      i.setInput(zipped,10,zipped.length-10);byte[] b=new byte[8192];
      while(!i.finished()) {int count=i.inflate(b);check(count>0||i.finished(),"gzip_truncated");check(out.size()+(long)count<=limit,"decompression_limit");out.write(b,0,count);}
      check(i.getRemaining()==8,"gzip_trailing");
      byte[] raw=out.toByteArray();CRC32 crc=new CRC32();crc.update(raw);
      ByteBuffer t=ByteBuffer.wrap(zipped,zipped.length-8,8).order(ByteOrder.LITTLE_ENDIAN);
      check(Integer.toUnsignedLong(t.getInt())==crc.getValue()&&Integer.toUnsignedLong(t.getInt())==raw.length,"gzip_footer");return raw;
    } catch(DataFormatException e){throw new Failure("gzip_corrupt");}finally{i.end();}
  }
  static List<JsonNode> rows(byte[] raw,String kind,int max) throws IOException {
    check(raw.length==0||raw[raw.length-1]==10,"ndjson_final_lf");var result=new ArrayList<JsonNode>();int start=0;
    for(int j=0;j<raw.length;j++)if(raw[j]==10){check(j>start&&j-start<=ROW&&result.size()<max,"ndjson_limit");JsonNode n=read(Arrays.copyOfRange(raw,start,j),ROW);require(kind,n);result.add(n);start=j+1;}
    return result;
  }
}
