package io.detectbridge.transport;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Map;
import org.junit.jupiter.api.Test;

class EnvelopeValidatorTest {
    @Test void sharedIndependentCases() throws Exception {
        var cases=Json.MAPPER.readTree(getClass().getResourceAsStream("/transport/v1/fixtures/validation-cases.json"));
        var validator=new EnvelopeValidator();
        for (var item:cases) {
            byte[] key=Base64.getDecoder().decode(item.get("key").asString());
            byte[] value=Base64.getDecoder().decode(item.get("value").asString());
            assertEquals(item.get("valid").asBoolean(),validator.validate(key,value)==null,item.get("name").asString());
        }
    }
    @Test void committedReplayExampleUsesDatasetIdentity() throws Exception {
        byte[] value=getClass().getResourceAsStream("/replay/v1/examples/record.json").readAllBytes();
        var node=Json.read(value);
        assertNull(new EnvelopeValidator().validate(node.get("run_id").asString().getBytes(StandardCharsets.UTF_8),value));
    }
    @Test void independentIdentityVectors() throws Exception {
        var cases=Json.MAPPER.readTree(getClass().getResourceAsStream("/v1/identity-vectors.json"));
        for (var item:cases) assertEquals(item.get("expected_id").asString(),"sha256:"+Json.sha(item.get("canonical_utf8").asString().getBytes(StandardCharsets.UTF_8)));
        assertEquals("sha256:3d606532f7bf626c422f403be33259be90e017ed947c5a3dc8517d571e981d52",Json.identity(java.util.List.of("test","host-a",java.util.List.of("native","record-1"))));
    }
    @Test void oversizedNestedAndNonlocalInput() {
        var validator=new EnvelopeValidator();
        assertNotNull(validator.validate(new byte[0],new byte[Json.MAX_VALUE+1]));
        assertNotNull(validator.validate(new byte[0],("[".repeat(70)+"0"+"]".repeat(70)).getBytes(StandardCharsets.UTF_8)));
        assertThrows(IllegalArgumentException.class,()->new EnvelopeValidator(Map.of("urn:test","{\"$ref\":\"https://example.invalid/blocked\"}")));
        assertNotNull(validator.validate(null,null));
    }
}
