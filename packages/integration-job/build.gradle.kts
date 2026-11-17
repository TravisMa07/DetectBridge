plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(project(":detection-evaluator"))
    implementation(project(":linux-adapters"))
    implementation(project(":windows-adapters"))
    implementation(libs.validator)
    testImplementation(libs.flink.streaming)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    implementation(libs.flink.kafka)
    implementation("org.apache.flink:flink-connector-base:2.2.1")
    compileOnly(libs.flink.streaming)
    compileOnly(libs.flink.clients)
}
application { mainClass.set("io.detectbridge.integration.IntegrationJob") }
tasks.shadowJar {
    archiveFileName.set("integration-job.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    filesMatching("v1/**") { duplicatesStrategy = DuplicatesStrategy.EXCLUDE }
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES",
            "FastDoubleParser-LICENSE", "FastDoubleParser-ThirdParty-LICENSE", "Schubfach-LICENSE")) {
        append("META-INF/$notice")
    }
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
}
configurations.runtimeClasspath { exclude(group = "org.slf4j") }

sourceSets.main { resources { srcDir(rootProject.file("contracts/integration-runtime/v1")); exclude("fixtures/**") } }
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
tasks.shadowJar { from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } } }
val prepareIntegrationCases = tasks.register<Exec>("prepareIntegrationCases") {
    workingDir(rootProject.projectDir)
    commandLine("uv", "run", "--locked", "python", "tools/integration_cases.py")
    inputs.files(rootProject.file("tools/integration_cases.py"), rootProject.file("tools/linux_assembly_cases.py"), rootProject.fileTree("packages/windows-adapters/fixtures"), rootProject.fileTree("packages/windows-adapters/profiles"), rootProject.fileTree("packages/linux-adapters/fixtures"), rootProject.fileTree("packages/linux-adapters/contracts"), rootProject.fileTree("tools") { include("detection_compile.py", "detection_mapping.py") })
    inputs.property("sourceRevision", providers.exec { commandLine("git", "rev-parse", "HEAD") }.standardOutput.asText)
    outputs.files(rootProject.file(".cache/integration/plan.json"), rootProject.file(".cache/integration/cases.json"))
}
tasks.test { dependsOn(prepareIntegrationCases); inputs.dir(rootProject.file(".cache/integration")); inputs.dir(rootProject.file("contracts/integration-runtime/v1/fixtures")) }
