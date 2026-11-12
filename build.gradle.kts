import org.gradle.api.plugins.JavaPluginExtension

plugins { base }

check(JavaVersion.current() == JavaVersion.VERSION_17) {
    "DetectBridge requires Java 17. Run python3 tools/dev.py bootstrap."
}

allprojects {
    dependencyLocking { lockAllConfigurations() }
    plugins.withId("java") {
        extensions.configure<JavaPluginExtension> {
            toolchain.languageVersion.set(JavaLanguageVersion.of(17))
        }
    }
}
