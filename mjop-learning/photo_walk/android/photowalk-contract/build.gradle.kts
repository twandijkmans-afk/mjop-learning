plugins { kotlin("jvm") version "1.9.24" }
repositories { mavenCentral() }
kotlin { jvmToolchain(17) }
dependencies { testImplementation(kotlin("test")) }
