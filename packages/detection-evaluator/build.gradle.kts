plugins {
    application
    alias(libs.plugins.shadow)
}
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(libs.validator)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
application { mainClass.set("io.detectbridge.detection.Evaluate") }
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("detection/v1/*.schema.json", "detection/v2/*.schema.json", "integration/v1/*.schema.json", "integration/v1.1/*.schema.json") } }
tasks.shadowJar {
    archiveFileName.set("evaluator.jar")
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
    filesMatching("v1/**") { duplicatesStrategy = DuplicatesStrategy.EXCLUDE }
    mergeServiceFiles()
    for (notice in listOf("LICENSE", "NOTICE", "LICENSE.txt", "NOTICE.txt", "DEPENDENCIES")) { append("META-INF/$notice") }
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    exclude("META-INF/*.SF", "META-INF/*.RSA", "META-INF/*.DSA", "module-info.class", "META-INF/versions/**/module-info.class")
}
val compileFixturePlan by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("uv", "run", "--locked", "python", "tools/check_mapping.py", "--prepare")
    inputs.files(rootProject.fileTree("contracts/detection/v1/fixtures"), rootProject.fileTree("contracts/v1"), rootProject.fileTree("contracts/detection/v2"))
    inputs.files(rootProject.fileTree("tools") { include("detection_compile.py", "detection_mapping.py", "check_mapping.py") }, rootProject.file("uv.lock"))
    outputs.files(rootProject.file(".cache/detection/plan.json"), rootProject.file(".cache/detection/mapped-plan.json"), rootProject.file(".cache/detection/selection-plan.json"))
}
tasks.test {
    dependsOn(compileFixturePlan)
    inputs.dir(rootProject.file("contracts/integration/v1/fixtures"))
    inputs.files(rootProject.fileTree("contracts/detection/v1/fixtures"), rootProject.fileTree("contracts/v1"), rootProject.fileTree("contracts/detection/v2"))
    inputs.files(rootProject.file(".cache/detection/plan.json"), rootProject.file(".cache/detection/mapped-plan.json"), rootProject.file(".cache/detection/selection-plan.json"))
}
