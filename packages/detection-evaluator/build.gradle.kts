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
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("detection/v1/*.schema.json") } }
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
    commandLine("uv", "run", "--locked", "python", "tools/detection.py", "prepare")
    inputs.files(rootProject.fileTree("contracts/detection/v1/fixtures"), rootProject.fileTree("contracts/v1"))
    inputs.files(rootProject.file("tools/detection_compile.py"), rootProject.file("uv.lock"))
    outputs.file(rootProject.file(".cache/detection/plan.json"))
}
tasks.test {
    dependsOn(compileFixturePlan)
    inputs.files(rootProject.fileTree("contracts/detection/v1/fixtures"), rootProject.fileTree("contracts/v1"))
    inputs.file(rootProject.file(".cache/detection/plan.json"))
}
