plugins { application }
repositories { mavenCentral() }
dependencies {
    implementation(project(":transport-contracts"))
    implementation(project(":detection-evaluator"))
    implementation(libs.validator)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
application { mainClass.set("io.detectbridge.windows.Offline") }
sourceSets.main { resources { srcDir("profiles"); include("*.source.json", "*.mapping.json") } }
sourceSets.test { resources { srcDir("profiles"); include("*.expected.json") } }
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
val prepareWindowsPlan = tasks.register<Exec>("prepareWindowsPlan") {
    workingDir(rootProject.projectDir)
    commandLine("uv", "run", "--locked", "python", "packages/windows-adapters/prepare.py")
    inputs.files(fileTree("profiles"), fileTree("fixtures/rules"), file("prepare.py"))
    inputs.files(rootProject.fileTree("tools") { include("detection_compile.py", "detection_mapping.py", "check_contracts.py") }, rootProject.file("uv.lock"))
    outputs.file(rootProject.file(".cache/windows/plan.json"))
}
tasks.test { dependsOn(prepareWindowsPlan, ":detection-evaluator:compileFixturePlan") }
