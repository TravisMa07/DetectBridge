plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(project(":archive-writer"))
    implementation(libs.validator)
    runtimeOnly(libs.slf4j.nop)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
application { mainClass.set("io.detectbridge.archive.LifecycleArchive") }
tasks.shadowJar {
    archiveFileName.set("lifecycle-archive.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES",
            "FastDoubleParser-LICENSE", "FastDoubleParser-ThirdParty-LICENSE", "Schubfach-LICENSE")) {
        append("META-INF/$notice")
    }
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
}

tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("lifecycle-runtime/v1/common.schema.json", "integration-runtime/v1/integration-registration.schema.json") } }
tasks.shadowJar { from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } } }
