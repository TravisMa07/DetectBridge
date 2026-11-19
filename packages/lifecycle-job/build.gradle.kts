plugins { java }
repositories { mavenCentral() }
dependencies {
    compileOnly(project(":integration-job"))
    compileOnly(project(":transport-contracts"))
    compileOnly(project(":detection-evaluator"))
    compileOnly(project(":linux-adapters"))
    compileOnly(project(":windows-adapters"))
    compileOnly(libs.flink.streaming)
    compileOnly(libs.flink.clients)
    compileOnly(libs.kafka.clients)
    compileOnly(libs.validator)
    testImplementation(project(":integration-job"))
    testImplementation(libs.flink.streaming)
    testImplementation(libs.flink.clients)
    testImplementation(libs.slf4j.nop)
    testImplementation(platform(libs.junit.bom))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
sourceSets.main { resources { srcDir(rootProject.file("contracts")); include("lifecycle-runtime/v1/*.schema.json", "lifecycle/v1/manifest.schema.json", "lifecycle-log4j.properties") } }
tasks.jar {
    archiveFileName.set("lifecycle-job.jar")
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
    from(rootProject.file("LICENSE")) { into("META-INF"); rename { "DetectBridge-LICENSE" } }
}
configurations.testImplementation { extendsFrom(configurations.compileOnly.get()) }
tasks.test { useJUnitPlatform(); systemProperty("repository.root", rootProject.projectDir) }
val qualification = sourceSets.create("qualification")
configurations[qualification.implementationConfigurationName].extendsFrom(configurations.compileOnly.get())
qualification.compileClasspath += sourceSets.main.get().output
val qualificationJar by tasks.registering(Jar::class) {
    dependsOn(tasks.named(qualification.classesTaskName))
    archiveFileName.set("lifecycle-probe.jar")
    from(qualification.output)
    isPreserveFileTimestamps = false
    isReproducibleFileOrder = true
}
val prepareLifecycleCases = tasks.register<Exec>("prepareLifecycleCases") {
    workingDir(rootProject.projectDir)
    commandLine("uv", "run", "--locked", "python", "packages/lifecycle-job/src/test/python/prepare.py")
    inputs.dir(rootProject.file("contracts/lifecycle-runtime/v1/fixtures"))
    inputs.file(project.file("src/test/python/prepare.py"))
    outputs.dir(project.file("build/fixtures"))
}
tasks.test { dependsOn(prepareLifecycleCases) }
