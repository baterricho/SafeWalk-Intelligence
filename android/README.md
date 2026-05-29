# SafeWalk Android APK

This Android project wraps the hosted SafeWalk Intelligence web app in an installable APK.

The GitHub Actions workflow builds `SafeWalk-Intelligence.apk` and uploads it to the `android-latest` GitHub release:

```text
https://github.com/baterricho/SafeWalk-Intelligence/releases/latest/download/SafeWalk-Intelligence.apk
```

The default app URL is configured in `app/build.gradle`:

```groovy
manifestPlaceholders = [
    webAppUrl: "https://safe-walk-intelligence.vercel.app/"
]
```

Change that value if the production site moves to another domain.
