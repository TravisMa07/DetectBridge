import java.io.DataInputStream;
import java.security.KeyFactory;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;

/** Verify a bounded batch using the JDK Ed25519 provider. No archive code enters the classpath. */
class LifecycleArchiveSignatures {
    private static byte[] field(DataInputStream input, int maximum) throws Exception {
        int length = input.readInt();
        if (length < 1 || length > maximum) throw new IllegalArgumentException();
        byte[] bytes = new byte[length];
        input.readFully(bytes);
        return bytes;
    }

    public static void main(String[] args) {
        try (var input = new DataInputStream(System.in)) {
            int count = input.readInt();
            if (count < 1 || count > 4096) throw new IllegalArgumentException();
            var factory = KeyFactory.getInstance("Ed25519");
            var verifier = Signature.getInstance("Ed25519");
            for (int i = 0; i < count; i++) {
                var key = factory.generatePublic(new X509EncodedKeySpec(field(input, 64)));
                verifier.initVerify(key);
                verifier.update(field(input, 524320));
                if (!verifier.verify(field(input, 64))) throw new IllegalArgumentException();
            }
            if (input.read() != -1) throw new IllegalArgumentException();
        } catch (Exception failure) {
            System.exit(1);
        }
    }
}
