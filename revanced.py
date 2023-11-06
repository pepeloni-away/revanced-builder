import os
import requests
import json
import subprocess
import sys
import re
import argparse
import random

def download_file(file_url: str, file_name: str):
    print("Downloading", file_url, "as", file_name)

    # Set the chunk size for downloading (adjust as needed)
    chunk_size = 1024  # 1 KB

    # Open the URL for downloading
    response = requests.get(file_url, stream=True)

    # Get the total file size from the response headers
    total_size = int(response.headers.get('content-length', 0))

    # Initialize variables to keep track of the download progress
    downloaded_bytes = 0

    # Open the file for writing in binary mode
    with open(file_name, 'wb') as file:
        for data in response.iter_content(chunk_size=chunk_size):
            file.write(data)
            downloaded_bytes += len(data)

            # Calculate the progress percentage
            progress_percent = (downloaded_bytes / total_size) * 100

            # Print a simple progress bar
            sys.stdout.write(f"\r[{'#' * int(progress_percent / 2)}{' ' * (50 - int(progress_percent / 2))}] [{int(progress_percent)}%]")
            sys.stdout.flush()
    print()

def update_revanced(repo: str, fallback_repo: str, cli: str, patches: str, integrations: str):
    def get_github_download_links(url, fallback_url=None, fallback_url1=None):
        response = requests.get(url)
        if response.status_code == 200:
            response = response.json()
            links = []
            for item in response["assets"]:
                links.append(item["name"])
                links.append(item["browser_download_url"])
            return links # [name, url(, name, url)*]
        else:
            print(f"Failed to get download link from {url}")
            if fallback_url1 and fallback_url != fallback_url1:
                print("Attempting with fallback url")
                return get_github_download_links(fallback_url, fallback_url1)
            elif fallback_url and url != fallback_url:
                print("Attempting with fallback url")
                return get_github_download_links(fallback_url)
            else:
                raise Exception("Failed to download one or more patching tools")

    def files_still_there():
        return (
            os.path.exists("cli.jar") and
            os.path.exists("patches.json") and
            os.path.exists("patches.jar") and
            os.path.exists("integrations.apk")
        )
    localfiles = []
    if os.path.exists(".revanced_versions.txt") and files_still_there():
        with open(".revanced_versions.txt", "r") as file:
            localfiles = [file.readline().strip() for _ in range(3)]

    with open(".revanced_versions.txt", "w") as file:
        pass

    # revanced-cli
    file_url = f"https://api.github.com/repos/{cli or repo}/revanced-cli/releases/latest"
    fallback_url = f"https://api.github.com/repos/{repo}/revanced-cli/releases/latest"
    fallback_url1 = f"https://api.github.com/repos/{fallback_repo}/revanced-cli/releases/latest" # the revanced repository
    cli_version, dl_url = get_github_download_links(file_url, fallback_url, fallback_url1)
    # download_file(dl_url, "cli.jar")
    if cli_version in localfiles:
        print("cli.jar is up-to-date")
    else:
        download_file(dl_url, "cli.jar")

    # revanced-patches
    file_url = f"https://api.github.com/repos/{patches or repo}/revanced-patches/releases/latest"
    fallback_url = f"https://api.github.com/repos/{repo}/revanced-patches/releases/latest"
    fallback_url1 = f"https://api.github.com/repos/{fallback_repo}/revanced-patches/releases/latest"

    patches_json, dl_url, patches_version, dl_url1 = get_github_download_links(file_url, fallback_url, fallback_url1)
    # download_file(dl_url, "patches.json")
    # download_file(dl_url1, "patches.jar")
    if patches_version in localfiles:
        print("patches.jar is up-to-date")
    else:
        download_file(dl_url, "patches.json")
        download_file(dl_url1, "patches.jar")

    # revanced-integrations
    file_url = f"https://api.github.com/repos/{integrations or repo}/revanced-integrations/releases/latest"
    fallback_url = f"https://api.github.com/repos/{repo}/revanced-integrations/releases/latest"
    fallback_url1 = f"https://api.github.com/repos/{fallback_repo}/revanced-integrations/releases/latest"

    integrations_version, dl_url = get_github_download_links(file_url, fallback_url, fallback_url1)
    # download_file(dl_url, "integrations.apk")
    if integrations_version in localfiles:
        print("integrations.apk is up-to-date")
    else:
        download_file(dl_url, "integrations.apk")

    with open(".revanced_versions.txt", "w") as file:
        file.write(cli_version + "\n")
        file.write(patches_version + "\n")
        file.write(integrations_version)

def get_apk(package_name: str, version: str):
    current_request = 0
    total_requests = 0
    last_progress_msg = ""
    bad_initial_progress_call = ""
    url = ""

    # update one line as we navigate apk host sites, looking for download urls
    # this function should be called once before the first request with the total number of requests, and then called empty before each subsequent request
    # reuse url for the request link, call with over="fail message" to move on to the next line
    def progress(steps: int=0, over: str=""):
        nonlocal current_request, total_requests, last_progress_msg, bad_initial_progress_call
        if steps > 0:
            current_request = 1
            total_requests = steps
            bad_initial_progress_call = ""
        else:
            current_request += 1
            if not bad_initial_progress_call and current_request > total_requests:
                bad_initial_progress_call = "fix your initial get_apk progress call!"
        # msg = f"Fetching [{current_request}/{total_requests}]: {f"[{bad_initial_progress_call}]{ over or url}" if bad_initial_progress_call else over or url}"
        msg = over or f"Fetching [{current_request}/{total_requests}]: {f"[{bad_initial_progress_call}]{url}" if bad_initial_progress_call else url}"
        spaces_to_clear = " " * len(last_progress_msg)
        print(f"\r{spaces_to_clear}", end="", flush=True)
        last_progress_msg = msg
        print(f"\r{msg}", end="", flush=True)
        if over or current_request >= total_requests:
            print()
    
    def log_version_on_success():
        with open(".apk_version.txt", "w") as file:
            file.write(f"{package_name}-{version}")

    # apkcombo is a good source but they shill their own apk installer with xapks as the only option sometimes
    # https://apkcombo.com/youtube/com.google.android.youtube/download/phone-18.38.44-apk case in point, whereas apkmirror provides the normal apk
    def apkcombo():
        nonlocal url
        # this is either 404 or redirects to the app page with the specified version        [[[[[[[[[do this for apkpure as well, pkg search redirect works]]]]]]]]]
        url = "https://apkcombo.com/search/" + package_name + "/download/" + ("apk" if version == "" else f"phone-{version}-apk")
        progress()
        response = requests.get(url, headers={"Referer": "https://apkcombo.com/"})
        if response.status_code == 404:
            progress(over="app not found on apkcombo!")
            return
        if response.status_code == 200:
            # https://download.apkcombo.com/com.google.android.youtube/YouTube_18.43.41_apkcombo.com.apk
            # ?ecp=Y29tLmdvb2dsZS5hbmRyb2lkLnlvdXR1YmUvMTguNDMuNDEvMTU0MDg4NTk1Mi41ODU3M2FmOGFhY2U5YjAxZmY0NTQwMDFhNGI4NDM2MzVhNGM0YjNhLmFwaw==
            # &iat=1699141714&sig=a4201aefd1136aaf098d1d5333988fa3&size=131564206&from=cf&version=old&lang=en
            regex = r'(?<=a href=")https://download\.apkcombo\.com/.*\.apk\?[^"]+'
            # for /r2?u=https..... external download links?, found at least on com.zhiliaoapp.musically
            regex2 = r'(?<=a href=")/r2.*\.apk[^"]+'
            url_fist_part = re.search(regex, response.text) or re.search(regex2, response.text)
            if url_fist_part == None:
                print("\ndid not find standalone apk for this app/version on apkcombo, doesn't exits?:", url)
                return
            else:
                url_fist_part = url_fist_part.group()
                if re.match(r"^http", url_fist_part) is None:
                    # this is partly urlencoded, requests should handle it though
                    url_fist_part = "https://download.apkcombo.com" + url_fist_part
                url = "https://apkcombo.com/checkin"
                progress()
                response = requests.get(url)
                if response.status_code == 200:
                    # fp=e1aa154442d600ccbfa78e01a042344e&ip=yourip
                    url_second_part = response.text
                    return url_fist_part + "&" + url_second_part
        print("apkcombo failed at url:", url)

    def apkmirror(found_app_url: str=""):
        nonlocal url
        base = "https://www.apkmirror.com"
        supported_apps = {
            "com.google.android.youtube": "https://www.apkmirror.com/apk/google-inc/youtube/",
            "com.google.android.apps.youtube.music": "https://www.apkmirror.com/apk/google-inc/youtube-music/"
        }
        if found_app_url:
            supported_apps[package_name] = found_app_url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        }
        if package_name in supported_apps:
            url = supported_apps[package_name]
            if not version:
                progress()
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    # this is the first list item and should be the latest version available
                    # /apk/google-inc/youtube/youtube-18-43-45-release/
                    regex = r'<div class="widgetHeader[^"]+">All versions <\/div>.*?<a class="fontBlack" href="([^"]+)'
                    match = re.search(regex, response.text, re.S)
                    if match:
                        url = base + match.group(1)
                    else:
                        progress(over="failed to find the latest version of " + package_name + " on apkmirror")
                        return
            else :
                slug = re.search(r"(?<=/)[^\/]+(?=\/$)", url).group()
                url = url + slug + f"-{version.replace('.', '-').replace(':', '')}-release"
            # url should look like this now: https://www.apkmirror.com/apk/google-inc/youtube/youtube-18-43-45-release/
            regex = r'(?<=apkm-badge">APK).*?href="([^"]+)'
            progress()
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                # https://www.apkmirror.com/apk/google-inc/youtube/youtube-18-38-44-release/youtube-18-38-44-2-android-apk-download/
                url = base + re.search(regex, response.text, re.S).group(1)

                regex = r'(?<=href=")(\/apk\/.*?\?key=\w+[^"]+)'
                progress()
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    # https://www.apkmirror.com/apk/google-inc/youtube/youtube-18-38-44-release/youtube-18-38-44-2-android-apk-download/
                    # download/?key=714ea56dd827493337e50628f937846729feaf94&forcebaseapk=true
                    url = base + re.search(regex, response.text).group(1).replace("&amp;", "&")

                    regex = r'<form id="filedownload".*?<\/form>'
                    progress()
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        download_form = re.search(regex, response.text, re.S).group()
                        if download_form:
                            parms = re.findall(r"name=\"([^\"]+)|value=\"([^\"]+)", download_form)
                            parms = list(map(lambda x: x[0] if parms.index(x) % 2 == 0 else x[1], parms))
                            url = (
                                base +
                                re.search(r'(?<=action=")([^"]+)', download_form).group() +
                                "?" +
                                "".join(["&" + value if index % 2 == 0 else "=" + value for index, value in enumerate(parms)])[1:]
                            )

                            progress()
                            response = requests.get(url, headers=headers, allow_redirects=False)
                            if response.status_code == 302:
                                return response.headers["Location"]
            print("apkmirror failed at url:", url)
        else:
            url = f'https://www.apkmirror.com/?post_type=app_release&searchtype=app&s="{package_name}"'
            response = requests.get(url, headers=headers)
            # print(response, response.text)
            # rate limited rn, if this is 200 take the first search result and recall apkmirror with it else print apkmirror doesnt have it

    localversion = []
    if os.path.exists(".apk_version.txt") and os.path.exists("apk.apk"):
        with open(".apk_version.txt", "r") as file:
            localversion = [file.readline().strip() for _ in range(1)]

    if f"{package_name}-{version}" in localversion:
        print("apk.apk is up-to-date")
        return

    with open(".apk_version.txt", "w") as file:
        pass

    apk_websites = [apkcombo, apkmirror]
    random.shuffle(apk_websites)
    download_link = None
    i = 0
    while download_link == None and i in range(0, len(apk_websites)):
        download_link = apk_websites[i]()
        i +=1
    print(download_link)
    assert download_link, "Completely failed to download apk"
    download_file(download_link, "apk.apk")

    log_version_on_success()

def select_options(user_input: str, option_list: list):
        selected_options = []
        if user_input == "":
            return
        for part in user_input.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                if start == 0 or end == 0 or start > len(option_list) or end > len(option_list):
                    raise IndexError()
                selected_options.extend(option_list[start - 1:end])
            else:
                if part == "" or int(part) == 0 or int(part) > len(option_list):
                    raise IndexError()
                selected_options.append(option_list[int(part) - 1])
        return selected_options

def get_selection_goal():
    print("Selection usage:")
    print("1. Only include the selected patches")
    print("2. Exclude the selected patches (from the default ones)")
    print("3. Include selected patches (together with default ones)")

    while True:
        try:
            choice = int(input("Enter the number of your choice: "))
            if choice in (1, 2, 3):
                return choice
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def check_java():
    cmd = ["java", "-version"]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        first_line = output.split("\n")[0]
        regex = r"^\w+ version \"?(\d{1,2})"
        version = int(re.match(regex, first_line).group(1))
        if version >= 11:
            return
        else:
            print("found incompatible java verson, revanced requires at least java 11")
            subprocess.run(cmd)
            sys.exit(1)
    except FileNotFoundError:
        print("java not found, install jdk11 or higher")
        sys.exit(1)

def check_keystore_type(keystore_file: str):
    print("Using keystore file:", os.path.abspath(keystore_file))
    command = ["keytool", "-list", "-keystore", keystore_file, "-storetype", "BKS", "-provider", "org.bouncycastle.jce.provider.BouncyCastleProvider",
               "-providerpath", "../bcprov-jdk18on-176.jar", "-storepass", ""]
    process = subprocess.run(command, capture_output=True, text=True)

    print("Checking keystore file --> ", end="")

    if process.returncode == 1 and "keytool error: java.lang.Exception: Keystore file does not exist:" in process.stdout:
        print("Keystore file does not exist yet, revanced cli will generate it in the patching process")
        return "to_be_generated"
    
    if process.returncode == 0 and "Your keystore contains 1 entry" in process.stdout:
        if "alias," in process.stdout:
            print("Old revanced key")
            return "old"
        if "ReVanced Key," in process.stdout:
            print("New revanced key")
            return "new"

    if process.returncode == 0 and "Your keystore contains 2 entries" in process.stdout and "alias," in process.stdout and "ReVanced Key," in process.stdout:
        print("Fixed keystore (see -h)")
        return "fixed"

    if process.returncode == 1 and 'java.lang.Exception: Provider "org.bouncycastle.jce.provider.BouncyCastleProvider" not found' in process.stdout:
        print("Keycheck failed as BouncyCastle jar file is missing from the working directory")

    print("Unexpected key, patching might fail")
    return "unexpected"

def main():
    default_repo = "revanced"

    parser = argparse.ArgumentParser(description="Build patched apps with ReVanced tools",
                                     epilog='The script looks for a general "revanced.keystore" file inside the working directory. ' +
                                     "Both pre and past revanced-cli4.0 keys are supported")
    parser.add_argument("-l", "--local", action="store_true", help="build using local files to avoid unnecessary re-downloads")
    parser.add_argument("repository", type=str, default=default_repo, nargs="?",
                        help="github username to download revanced-cli, patches and integrations form, " +
                        "also acts as download folder (default and fallback: %(default)s)")
    parser.add_argument("--cli", type=str, default=None, help="github username to download revanced-cli from (priority over repository)")
    parser.add_argument("--patches", type=str, default=None, help="github username to download revanced-patches from (priority over repository)")
    parser.add_argument("--integrations", type=str, default=None, help="github username to download revanced-integrations from (priority over repository)")
    parser.add_argument("-a", "--app", "--package", nargs="?", const="", default="com.google.android.youtube",
                        help="specify an app to patch or be prompted to choose based on patches (default: %(default)s). " +
                        "The script will scan the working directory for apk files before trying to download when this option is used. " +
                        "No checks are done with this option, you can provide any apk and use at least the universal patches on it")

    args = parser.parse_args()

    check_java()

    for folder in ["_builds", args.repository]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    os.chdir(args.repository)

    if not args.local:
        update_revanced(args.repository, default_repo, args.cli, args.patches, args.integrations)

    all_apps = []
    app_patches = []
    recomended_version = ""
    with open("patches.json", "r") as file:
        data = json.load(file)

    if args.app == "":
        for key in data:
            if key["compatiblePackages"] == None:
                continue
            for package in key["compatiblePackages"]:
                if package["name"] not in all_apps:
                    all_apps.append(package["name"])
        all_apps.sort()
        for i, item in enumerate(all_apps, start=1):
            print(f"{i:{len(str(len(all_apps)))}}. {item}")
        while True:
            try:
                user_input = int(input("Select app to patch: ")) - 1
                if user_input in range(0, len(all_apps)):
                    args.app = all_apps[user_input]
                    break
                else:
                    raise IndexError()
            except IndexError:
                print("Invalid selection.")

    for key in data:
        # include universal patches
        if key["compatiblePackages"] == None:
            app_patches.append(key)
            continue
        for package in key["compatiblePackages"]:
            if package["name"] == args.app:
                app_patches.append(key)
                # this isn't optimal but so far patches were updated all at once so it works
                if not recomended_version and package["versions"]:
                    recomended_version = package["versions"][-1]
                    print("Presuming recomended youtube version:", recomended_version)
    
    if not args.local:
        get_apk(args.app, recomended_version)

    all_options = map(lambda x: f'{x["name"]} - {x["description"]}' if x["use"] else "(-) " + f'{x["name"]} - {x["description"]}', app_patches)

    for i, item in enumerate(all_options, start=1):
        # print(f"{i}. {item}")
        print(f"{i:{len(str(len(app_patches)))}}. {item}")

    print('"(-)" prefix means excluded by defalut')
    while True:
        try:
            user_input = input("Select patches e.g. 1,4,7,8-12,14 or empty for default: ")
            selected_options = select_options(user_input, app_patches)
            break
        except IndexError:
            print("Invalid selection.")

    keystore_file = "../revanced.keystore" if os.path.exists(os.path.join(os.path.dirname(os.getcwd()), "revanced.keystore")) else "revanced.keystore"
    base_command = ["java", "-jar", "cli.jar", "patch", "--patch-bundle=patches.jar", "--merge=integrations.apk", "--keystore=" + keystore_file,
                    f"--out=../_builds/revanced({args.repository})[{args.app.replace(".", "_")}].apk", "apk.apk"]

    # cli 4.0 doesn't work with old keys
    # https://github.com/ReVanced/revanced-cli/issues/277
    # https://github.com/ReVanced/revanced-cli/issues/272

    # we are in a situation where revanced-cli only works with new keys and inotia00's fork only works with old keys.....
    compatibility_patch_old_key = ["--alias=alias", "--keystore-entry-password=ReVanced", "--keystore-password=ReVanced"]
    compatibility_patch_new_key = ["--alias=ReVanced Key", "--keystore-entry-password=", "--keystore-password="]

    if selected_options:
        user_input = get_selection_goal()

        if user_input == 1:
            base_command.append("--exclusive")
            for patch in selected_options:
                base_command.append(f'--include={patch["name"]}')
        elif user_input == 2:
            for patch in selected_options:
                base_command.append(f'--exclude={patch["name"]}')
        else:
            for patch in selected_options:
                base_command.append(f'--include={patch["name"]}')

    key_type = check_keystore_type(keystore_file)
    if key_type == "old":
        base_command += compatibility_patch_old_key
    if key_type == "new":
        base_command += compatibility_patch_new_key

    printable_command = [f'{item.split("=")[0]}="{item.split("=")[1]}"' if " " in item else item for item in base_command]
    printable_command = [f'{item.split("=")[0]}=""' if re.match(r".*=$", item) else item for item in printable_command]
    print("Running:", " ".join(printable_command))
    subprocess.run(base_command)

if __name__ == "__main__":
    main()
