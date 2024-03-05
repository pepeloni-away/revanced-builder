# revanced-builder
another revanced builder, the goal for this was to be able to select the patches you want and to work on most things, including inside termux
## other features
* support forks of official revanced tools, be it just one or all 3 (revanced-cli, revanced-patches, revanced-integrations)
* sign all builds with one key and handle the compatibility issues brought by [revanced-cli v4.0](https://github.com/ReVanced/revanced-cli/releases/tag/v4.0.0)
* try to download all current and and future supported revanced apps from multiple sources (apkpure, apkcombo, apkmirror)
* allow patching any user-provided apk file with at least the universal patches

# usage
you will need python to run the script and Java SDK 11 (Azul Zulu JDK or OpenJDK) as per [revanced documentation](https://github.com/ReVanced/revanced-cli/blob/main/docs/0_prerequisites.md#-prerequisites)  
you might need to install the requests python package if it isn't already installed `pip install requests`  

clone the repo and run `python revanced.py` to build youtube revanced, after downloading or checking if revanced tools are up-to-date you will be asked to select patches and what to do with them.  
you can use `python revanced.py -a` to be promted to select a different app based on patches, or provide a package name for an app yourself `python revanced.py -a tv.twitch.android.app`.

`python revanced.py inotia00` builds with revanced-cli, revanced-patches and revanced-integrations from [inotia00](https://github.com/inotia00?tab=repositories)

`python revanced.py YT-Advanced --patches YT-Advanced/ReX-patches --integrations YT-Advanced/ReX-integrations` builds with ReX-patches and Rex-integrations from [YT-Advanced](https://github.com/YT-Advanced?tab=repositories) and falls back to revanced-cli

### -h output
\* probably not up to date, it's annoying to format this nicely after updates
```
usage: revanced.py [-h] [-l] [-e] [--cli CLI] [--patches PATCHES] [--integrations INTEGRATIONS] [-a [APP]] [repository]

Build patched apps with ReVanced tools

positional arguments:
  repository            github username to download revanced-cli, patches and integrations form, also acts as download folder (default and fallback: revanced)

options:
  -h, --help            show this help message and exit
  -l, --local           build using local files to avoid unnecessary github api requests(max 60/h) and re-downloads
  -e, --export          stop after printing the patch command instead of running it
  --cli CLI             github username to download revanced-cli from (priority over repository)
  --patches PATCHES     github username to download revanced-patches from (priority over repository)
  --integrations INTEGRATIONS
                        github username to download revanced-integrations from (priority over repository)
  -a [APP], --app [APP], --package [APP]
                        specify an app to patch or be prompted to choose based on patches (default: com.google.android.youtube). The script will scan the working directory for apk files before trying to
                        download when this option is used. No checks are done with this option, you can provide any apk and use at least the universal patches on it

The script looks for a general "revanced.keystore" file inside the working directory. Both pre and past revanced-cli4.0 keys are supported
```
