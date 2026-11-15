plugins { `java-library` }
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(project(":detection-evaluator"))
    implementation(libs.validator)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
sourceSets.main { resources { srcDir("contracts"); exclude("*.contract-example.event.json") } }
sourceSets.test { resources { srcDir("contracts"); include("*.contract-example.event.json") } }
val prepareLinuxCases by tasks.registering(Exec::class) {
    workingDir(rootProject.projectDir)
    commandLine("uv", "run", "--locked", "python", "packages/linux-adapters/fixtures/prepare_cases.py")
    inputs.files(fileTree("fixtures"), fileTree("contracts"), rootProject.fileTree("tools") { include("detection_compile.py", "detection_mapping.py", "check_contracts.py") }, rootProject.file("uv.lock"))
    outputs.dir(rootProject.file(".cache/linux-adapters/plans"))
}
tasks.test { dependsOn(prepareLinuxCases); inputs.dir(rootProject.file(".cache/linux-adapters/plans")) }
