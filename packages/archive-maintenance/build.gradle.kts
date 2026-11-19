import com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar

plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(libs.validator)
    runtimeOnly(libs.slf4j.nop)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
application { mainClass.set("io.detectbridge.archive.ManagedMain") }
// Preserve the original archive module/JAR; only these pinned source primitives are reused.
val legacySources by tasks.registering(Sync::class) {
    from(rootProject.file("packages/archive-writer/src/main/java")) {
        include("io/detectbridge/archive/Format.java", "io/detectbridge/archive/Store.java", "io/detectbridge/archive/Main.java")
    }
    into(layout.buildDirectory.dir("generated/legacy"))
}
sourceSets.main {
    java.srcDir(legacySources.map { it.destinationDir })
    resources {
        srcDir(rootProject.file("contracts"))
        include("archive/v1/*.schema.json", "archive-maintenance/v1/*.schema.json")
    }
}
tasks.compileJava { dependsOn(legacySources) }
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir); inputs.dir(rootProject.file("contracts/archive-maintenance/v1")) }
tasks.shadowJar {
    archiveFileName.set("archive-maintenance.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES",
            "FastDoubleParser-LICENSE", "FastDoubleParser-ThirdParty-LICENSE", "Schubfach-LICENSE")) append("META-INF/$notice")
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
    from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } }
    from(rootProject.file("contracts/v1/NOTICE")) { into("META-INF"); rename { "ECS-NOTICE" } }
}

// Bind the standalone controller, exact local import rules and unchanged source primitives.
tasks.shadowJar {
    from(rootProject.file("tools")) {
        include("archive_maintenance.py", "archive_profiles.py", "managed_replay.py", "p05_archive.py", "replay.py",
            "replay_time.py", "check_replay.py", "check_datasets.py", "datasets.py",
            "contract_identity.py", "check_contracts.py")
        into("META-INF/maintenance/tools")
    }
    from(rootProject.file("uv.lock")) { into("META-INF/maintenance") }
    for (directory in listOf("archive-maintenance/v1", "replay/v1", "v1")) {
        from(rootProject.file("contracts/$directory")) {
            include("*.schema.json"); into("META-INF/maintenance/contracts/$directory")
        }
    }
    from(rootProject.file("catalog/datasets/manifest.schema.json")) {
        into("META-INF/maintenance/catalog/datasets")
    }
    from(rootProject.file("packages/archive-writer/src/main/java/io/detectbridge/archive")) {
        include("Format.java", "Store.java", "Main.java"); into("META-INF/maintenance/legacy")
    }
}

// A separate executable qualification artifact; no test/probe classes enter the managed JAR.
val qualificationJar by tasks.registering(ShadowJar::class) {
    dependsOn(tasks.testClasses)
    archiveFileName.set("archive-maintenance-probe.jar")
    configurations = listOf(project.configurations.testRuntimeClasspath.get())
    from(sourceSets.main.get().output)
    from(sourceSets.test.get().output)
    manifest { attributes["Main-Class"] = "io.detectbridge.archive.ManagedProbe" }
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES",
            "FastDoubleParser-LICENSE", "FastDoubleParser-ThirdParty-LICENSE", "Schubfach-LICENSE")) append("META-INF/$notice")
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
}

// Exact local schemas describe understood reference graphs; unknown profiles remain blockers.
tasks.processResources {
    from(rootProject.projectDir) {
        include(
            "contracts/v1/common.schema.json",
            "contracts/v1/raw-record.schema.json",
            "contracts/v1/normalized-event.schema.json",
            "contracts/detection/v2/candidate-provenance.schema.json",
            "contracts/integration/v1.1/common.schema.json",
            "contracts/integration/v1.1/tagged-event.schema.json",
            "contracts/integration/v1.1/detection.schema.json",
            "contracts/integration/v1.1/diagnostic.schema.json",
            "contracts/integration-runtime/v1/integration-input.schema.json",
            "contracts/integration-runtime/v1/integration-receipt.schema.json",
            "contracts/integration-runtime/v1/integration-preservation.schema.json",
            "packages/linux-adapters/contracts/context.schema.json",
            "packages/linux-adapters/contracts/context-extension.schema.json",
            "packages/linux-adapters/contracts/manifest.schema.json",
            "packages/linux-adapters/contracts/preservation.schema.json",
        )
        into("archive-graph")
    }
}
