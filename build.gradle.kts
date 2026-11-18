import org.gradle.api.plugins.JavaPluginExtension
import org.gradle.api.artifacts.component.ModuleComponentIdentifier

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

// CI prepares one public module cache before parallel consumers. No source/test tasks run.
tasks.register("ciDependencies") {
    doLast {
        allprojects.sortedBy { it.path }.forEach { project ->
            project.configurations.filter { it.isCanBeResolved }.sortedBy { it.name }.forEach { configuration ->
                configuration.incoming.artifactView {
                    componentFilter { it is ModuleComponentIdentifier }
                }.files.files
            }
        }
    }
}

// Patch vulnerable transitive codecs/tooling without changing the agreed primary pins.
val reviewedPatches = mapOf(
    "at.yawk.lz4:lz4-java" to libs.versions.lz4.get(),
    "org.xerial.snappy:snappy-java" to libs.versions.snappy.get(),
    "com.fasterxml.jackson.core:jackson-core" to libs.versions.jacksonLegacy.get(),
    "com.fasterxml.jackson.core:jackson-databind" to libs.versions.jacksonLegacy.get()
)
allprojects {
    configurations.configureEach {
        resolutionStrategy.eachDependency {
            reviewedPatches["${requested.group}:${requested.name}"]?.let {
                useVersion(it)
                because("P07 reviewed security patch; see docs/transport-dependencies.md")
            }
        }
    }
    buildscript.configurations.configureEach {
        resolutionStrategy.eachDependency {
            reviewedPatches["${requested.group}:${requested.name}"]?.let {
                useVersion(it)
                because("P07 reviewed build-tool security patch")
            }
        }
    }
}
