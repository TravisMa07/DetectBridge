plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(project(":detection-evaluator"))
    implementation(project(":linux-adapters"))
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
application { mainClass.set("io.detectbridge.assembly.AssemblyJob") }
tasks.shadowJar {
    archiveFileName.set("linux-assembly-job.jar")
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

sourceSets.main { resources { srcDir(rootProject.file("contracts/linux-assembly/v1")); exclude("fixtures/**") } }
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
val prepareAssemblyCases by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("uv", "run", "--locked", "python", "tools/linux_assembly_cases.py")
    inputs.file(rootProject.file("tools/linux_assembly_cases.py"))
    inputs.file(rootProject.file("contracts/linux-assembly/v1/fixtures/identity-vectors.json"))
    inputs.files(rootProject.fileTree("packages/linux-adapters/contracts"))
    outputs.file(rootProject.file(".cache/linux-assembly/cases.json"))
}
tasks.test { dependsOn(prepareAssemblyCases); inputs.file(rootProject.file(".cache/linux-assembly/cases.json")) }
tasks.shadowJar {
    from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } }
}
