# Deployment: Hermes Android GUI
**Requirements:** [docs/requirements/hermes-android-gui.md](../requirements/hermes-android-gui.md)
**Architecture:** [docs/architecture/hermes-android-gui.md](../architecture/hermes-android-gui.md)
**Date:** 2026-06-12

---

## 1. Build & Run

### Prerequisites
- **Android Studio** Hedgehog (2023.1.1) or newer
- **JDK 17**
- **Android SDK** 34 with build tools 34.0.0
- **Gradle 8.5** (wrapper included)

### Opening the Project
```bash
# Open in Android Studio
studio /home/user/dev/Opencode
# Or open the directory directly from Android Studio welcome screen
```

### Build from CLI
```bash
cd /home/user/dev/Opencode

# Debug APK
./gradlew assembleDebug

# Release APK (requires signing key)
./gradlew assembleRelease

# Install on connected device
./gradlew installDebug
```

### APK Locations
- Debug: `app/build/outputs/apk/debug/app-debug.apk`
- Release: `app/build/outputs/apk/release/app-release.apk`

---

## 2. Configuration

### First Run
1. Install the APK on your Android device
2. Open the app
3. Go to **Настройки** (Settings tab)
4. Configure:
   - **URL API-сервера**: Your Hermes API server address
     - If Hermes is on the same machine's Docker/VM and phone is on the same WiFi: `http://192.168.x.x:8642`
     - If Hermes is on localhost of Android: `http://10.0.2.2:8642` (Android emulator) or `http://localhost:8642`
   - **API-ключ**: Your `API_SERVER_KEY` from Hermes `.env` file
5. Return to Chat tab and start messaging

### Hermes Server Setup
Ensure Hermes agent API server is running:
```bash
# In Hermes agent directory
hermes gateway
# Or check .env:
# API_SERVER_ENABLED=true
# API_SERVER_KEY=your_key_here
```

The API server listens on `http://127.0.0.1:8642` by default.

---

## 3. Release Signing

Create a keystore and configure signing in `app/build.gradle.kts`:

```kotlin
android {
    signingConfigs {
        create("release") {
            storeFile = file("hermes-gui.keystore")
            storePassword = System.getenv("KEYSTORE_PASSWORD")
            keyAlias = "hermes-gui"
            keyPassword = System.getenv("KEY_PASSWORD")
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

---

## 4. CI/CD (GitHub Actions)

```yaml
name: Build APK
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - run: ./gradlew assembleDebug
      - uses: actions/upload-artifact@v4
        with:
          name: debug-apk
          path: app/build/outputs/apk/debug/
```

---

## 5. Monitoring

- Local logs via `adb logcat | grep HermesGUI`
- Room DB inspection via Database Inspector in Android Studio
- Network calls visible in Logcat with OkHttp logging interceptor

---

## 6. Permissions

| Permission | Purpose |
|-----------|---------|
| INTERNET | API communication |
| ACCESS_NETWORK_STATE | Connection status detection |
