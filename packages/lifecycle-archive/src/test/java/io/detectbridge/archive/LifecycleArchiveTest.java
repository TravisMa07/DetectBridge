package io.detectbridge.archive;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;

class LifecycleArchiveTest {
    @Test void preservesBrokerAcceptedPhysicalOutputBeyondLegacyLimit() {
        assertDoesNotThrow(() -> LifecycleArchive.verifyValue("output", new byte[2 * Format.MIB + 65536]));
        assertThrows(Format.Failure.class, () -> LifecycleArchive.verifyValue("output", new byte[4 * Format.MIB + 1]));
    }
}
