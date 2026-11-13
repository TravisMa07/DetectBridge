package io.detectbridge.transport;

import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import tools.jackson.core.StreamReadConstraints;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.core.json.JsonFactory;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

public final class Json {
    public static final int MAX_VALUE = 1024 * 1024;
    public static final JsonMapper MAPPER = JsonMapper.builder(JsonFactory.builder()
        .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
        .streamReadConstraints(StreamReadConstraints.builder().maxNestingDepth(64)
            .maxStringLength(MAX_VALUE).maxNumberLength(128).build()).build())
        .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
    private Json() {}
    public static JsonNode read(byte[] data) {
        if (data == null || data.length > MAX_VALUE) throw new IllegalArgumentException("value_limit");
        try {
            StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data));
            JsonNode value = MAPPER.readTree(data);
            if (value == null) throw new IllegalArgumentException("empty_json");
            return value;
        } catch (Exception ex) { throw new IllegalArgumentException("invalid_json"); }
    }
    public static byte[] bytes(Object value) { return MAPPER.writeValueAsBytes(value); }
    public static String sha(byte[] bytes) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (Exception ex) { throw new IllegalStateException("digest_unavailable"); }
    }
    public static String identity(Object value) { return "sha256:" + sha(bytes(value)); }
}
