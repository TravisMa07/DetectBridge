package io.detectbridge.windows;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;
import javax.xml.XMLConstants;
import javax.xml.parsers.SAXParserFactory;
import org.xml.sax.*;
import org.xml.sax.helpers.DefaultHandler;

/** Streaming bounds apply before building any vendor-field representation. */
final class WindowsXml extends DefaultHandler {
  static final String NS = "http://schemas.microsoft.com/win/2004/08/events/event";
  final Map<String, String> system = new LinkedHashMap<>(), data = new LinkedHashMap<>();
  final Map<String, Map<String, String>> attributes = new LinkedHashMap<>();
  final Deque<String> path = new ArrayDeque<>();
  final Set<String> seen = new HashSet<>();
  StringBuilder scalar;
  String field;
  int nodes;

  static WindowsXml parse(byte[] bytes) throws Exception {
    if (bytes.length == 0 || bytes.length > 1024 * 1024) throw new SAXException("limit");
    String text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
    for (int i = 0; i < text.length() - 1; i++) if (text.charAt(i) == '\n') throw new SAXException("framing");
    var factory = SAXParserFactory.newInstance();
    factory.setNamespaceAware(true); factory.setXIncludeAware(false);
    factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
    factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
    var reader = factory.newSAXParser().getXMLReader();
    reader.setProperty(XMLConstants.ACCESS_EXTERNAL_DTD, "");
    reader.setProperty(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
    var handler = new WindowsXml();
    reader.setContentHandler(handler); reader.setErrorHandler(handler);
    reader.setEntityResolver((publicId, systemId) -> { throw new SAXException("external_resource"); });
    // A character stream prevents XML's encoding declaration from overriding UTF-8.
    reader.parse(new InputSource(new StringReader(text)));
    if (!handler.seen.contains("Event/System") || !handler.seen.contains("Event/EventData")) throw new SAXException("structure");
    return handler;
  }
  private static void limit(String value) throws SAXException {
    if (value.getBytes(StandardCharsets.UTF_8).length > 65536) throw new SAXException("scalar_limit");
  }
  @Override public void startElement(String uri, String local, String qName, Attributes attrs) throws SAXException {
    if (!uri.equals(NS) || ++nodes > 4096 || path.size() >= 32 || scalar != null) throw new SAXException("structure_or_limit");
    path.addLast(local);
    String p = String.join("/", path);
    boolean leaf = path.size() == 3;
    if (path.size() == 1 && !local.equals("Event")
        || path.size() == 2 && !Set.of("System", "EventData").contains(local)
        || path.size() > 3
        || leaf && path.toArray()[1].equals("EventData") && !local.equals("Data")) throw new SAXException("structure");
    if (!p.equals("Event/EventData/Data") && !seen.add(p)) throw new SAXException("duplicate");
    Map<String, String> a = new LinkedHashMap<>();
    for (int i = 0; i < attrs.getLength(); i++) {
      if (!attrs.getURI(i).isEmpty()) throw new SAXException("attribute_namespace");
      limit(attrs.getValue(i)); limit(attrs.getLocalName(i));
      a.put(attrs.getLocalName(i), attrs.getValue(i));
    }
    if (leaf) {
      if (p.equals("Event/EventData/Data")) {
        if (a.size() != 1 || !a.containsKey("Name") || a.get("Name").isEmpty() || data.size() >= 256
            || data.containsKey(a.get("Name"))) throw new SAXException("field");
        field = a.get("Name");
        data.put(field, "");
      } else attributes.put(local, a);
      scalar = new StringBuilder();
    } else if (!a.isEmpty()) throw new SAXException("container_attributes");
  }
  @Override public void characters(char[] c, int start, int length) throws SAXException {
    if (scalar != null) {
      scalar.append(c, start, length);
      // SAX may split surrogate pairs; exact UTF-8 bound is checked at endElement.
      if (scalar.length() > 65536) throw new SAXException("scalar_limit");
    } else for (int i = start; i < start + length; i++) if (!Character.isWhitespace(c[i])) throw new SAXException("container_text");
  }
  @Override public void endElement(String uri, String local, String qName) throws SAXException {
    if (scalar != null) {
      String value = scalar.toString(); limit(value);
      if (local.equals("Data")) data.put(field, value); else system.put(local, value);
      scalar = null;
    }
    path.removeLast();
  }
  @Override public void processingInstruction(String target, String data) throws SAXException { throw new SAXException("processing_instruction"); }
  @Override public void error(SAXParseException e) throws SAXException { throw e; }
  @Override public void fatalError(SAXParseException e) throws SAXException { throw e; }
}
