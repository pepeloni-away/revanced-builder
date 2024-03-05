import requests

import os
import json
import subprocess
import sys
import re
import argparse
import random
import shutil

def download_file(file_url: str, file_name: str):
    print("Downloading", file_url, "as", file_name)

    chunk_size = 1024
    response = requests.get(file_url, stream=True)
    total_size = int(response.headers.get("content-length", 0))
    downloaded_bytes = 0

    # Open the file for writing in binary mode
    with open(file_name, "wb") as file:
        for data in response.iter_content(chunk_size=chunk_size):
            file.write(data)
            downloaded_bytes += len(data)

            if total_size == 0:
                print(
                    f"\r[{downloaded_bytes} bytes / unknown] [?%]", end="", flush=True
                )
            else:
                progress_percent = (downloaded_bytes / total_size) * 100

                max_length = shutil.get_terminal_size()[0] - 10
                progress = "#" * int(progress_percent / 100 * max_length)
                empty = " " * (max_length - len(progress))

                # 8 fixed characters here, 4 square brackets, 1 space, 1 percent sign, 2 percent digits
                print(
                    f"\r[{progress}{empty}] [{int(progress_percent)}%]",
                    end="",
                    flush=True,
                )
    print()


def update_revanced(
    repo: str, fallback_repo: str, cli: str, patches: str, integrations: str
):
    def get_github_download_links(url, fallback_url=None, fallback_url1=None):
        response = requests.get(url)
        if response.status_code == 200:
            response = response.json()
            links = []
            for item in response["assets"]:
                links.append(item["name"])
                links.append(item["browser_download_url"])
            return links  # [name, url(, name, url)*]
        else:
            print(f"Failed to get download link from {url}")
            if fallback_url1 and fallback_url != fallback_url1:
                print("Attempting with fallback url")
                return get_github_download_links(fallback_url, fallback_url1)
            elif fallback_url and url != fallback_url:
                print("Attempting with fallback url")
                return get_github_download_links(fallback_url)
            else:
                print(
                    "Exiting: Failed to get download urls for one or more patching tools"
                )
                sys.exit(1)

    def files_still_there():
        return (
            os.path.exists("cli.jar")
            and os.path.exists("patches.json")
            and os.path.exists("patches.jar")
            and os.path.exists("integrations.apk")
        )

    localfiles = []
    if os.path.exists(".revanced_versions.txt") and files_still_there():
        with open(".revanced_versions.txt", "r") as file:
            localfiles = [file.readline().strip() for _ in range(3)]

    with open(".revanced_versions.txt", "w") as file:
        pass

    # revanced-cli
    file_url = (
        f"https://api.github.com/repos/{cli or repo}/revanced-cli/releases/latest"
    )
    fallback_url = f"https://api.github.com/repos/{repo}/revanced-cli/releases/latest"
    fallback_url1 = f"https://api.github.com/repos/{fallback_repo}/revanced-cli/releases/latest"  # the revanced repository
    cli_version, dl_url = get_github_download_links(
        file_url, fallback_url, fallback_url1
    )
    if cli_version in localfiles:
        print("cli.jar is up-to-date")
    else:
        download_file(dl_url, "cli.jar")

    # revanced-patches
    file_url = f"https://api.github.com/repos/{patches or repo}/revanced-patches/releases/latest"
    fallback_url = (
        f"https://api.github.com/repos/{repo}/revanced-patches/releases/latest"
    )
    fallback_url1 = (
        f"https://api.github.com/repos/{fallback_repo}/revanced-patches/releases/latest"
    )

    temp = get_github_download_links(file_url, fallback_url, fallback_url1)
    temp = list(filter(lambda x: ".asc" not in x, temp))
    patches_json, dl_url, patches_version, dl_url1 = temp
    if patches_version in localfiles:
        print("patches.jar is up-to-date")
    else:
        download_file(dl_url, "patches.json")
        download_file(dl_url1, "patches.jar")

    # revanced-integrations
    file_url = f"https://api.github.com/repos/{integrations or repo}/revanced-integrations/releases/latest"
    fallback_url = (
        f"https://api.github.com/repos/{repo}/revanced-integrations/releases/latest"
    )
    fallback_url1 = f"https://api.github.com/repos/{fallback_repo}/revanced-integrations/releases/latest"

    temp = get_github_download_links(file_url, fallback_url, fallback_url1)
    temp = list(filter(lambda x: ".asc" not in x, temp))
    integrations_version, dl_url = temp
    if integrations_version in localfiles:
        print("integrations.apk is up-to-date")
    else:
        download_file(dl_url, "integrations.apk")

    with open(".revanced_versions.txt", "w") as file:
        file.write("\n".join([cli_version, patches_version, integrations_version]))


def get_apk(package_name: str, version: str, local: bool, scan_folder_for_apks: bool):
    default_apk = "app.apk"
    url = ""

    def scan_for_apk_files(folder_path):
        files = os.listdir(folder_path)

        apk_files = [file for file in files if file.endswith(".apk")]

        return apk_files

    current_request = 0
    total_requests = 0
    last_progress_msg = ""

    # update one line as we navigate apk host sites, looking for download urls
    # this function should be called once before the first request with the total number of requests, and then called empty before each subsequent request
    # reuse url for the request link, call with over="<fail message>" to move on a new line early
    def progress(steps: int = 0, over: str = ""):
        nonlocal current_request, total_requests, last_progress_msg
        if steps > 0:
            current_request = 1
            total_requests = steps
        else:
            current_request += 1
        msg = over or f"Fetching [{current_request}/{total_requests}]: {url}"
        spaces_to_clear = " " * len(last_progress_msg)
        print(f"\r{spaces_to_clear}", end="", flush=True)
        last_progress_msg = msg
        print(f"\r{msg}", end="", flush=True)
        if over or current_request >= total_requests:
            print()

    # apkcombo is a good source but they shill their own apk installer with xapks as the only option sometimes
    # https://apkcombo.com/youtube/com.google.android.youtube/download/phone-18.38.44-apk case in point, whereas apkmirror provides the normal apk
    def apkcombo():
        nonlocal url
        # this is either 404 or redirects to the app page with the specified version
        url = (
            "https://apkcombo.com/search/"
            + package_name
            + "/download/"
            + ("apk" if version == "" else f"phone-{version}-apk")
        )
        progress(2)
        response = requests.get(url, headers={"Referer": "https://apkcombo.com/"})
        if response.status_code == 404:
            progress(over="app not found on apkcombo!")
            return
        if response.status_code == 200:
            # https://download.apkcombo.com/com.google.android.youtube/YouTube_18.43.41_apkcombo.com.apk
            # ?ecp=Y29tLmdvb2dsZS5hbmRyb2lkLnlvdXR1YmUvMTguNDMuNDEvMTU0MDg4NTk1Mi41ODU3M2FmOGFhY2U5YjAxZmY0NTQwMDFhNGI4NDM2MzVhNGM0YjNhLmFwaw==
            # &iat=1699141714&sig=a4201aefd1136aaf098d1d5333988fa3&size=131564206&from=cf&version=old&lang=en
            regex = r'(?<=a href=")https://download\.apkcombo\.com/.*\.apk\?[^"]+'
            # for /r2?u=https..... external download links?, found at least on com.zhiliaoapp.musically, guardian tales
            regex2 = r'(?<=a href=")/r2.*\.apk[^"]+'
            url_fist_part = re.search(regex, response.text) or re.search(
                regex2, response.text
            )
            if url_fist_part == None:
                progress(
                    over="did not find standalone apk for this app/version on apkcombo, doesn't exits? "
                    + url
                )
                return
            else:
                url_fist_part = url_fist_part.group()
                if re.match(r"^http", url_fist_part) is None:
                    url_fist_part = "https://apkcombo.com" + url_fist_part
                url = "https://apkcombo.com/checkin"
                progress()
                response = requests.get(url)
                if response.status_code == 200:
                    # fp=e1aa154442d600ccbfa78e01a042344e&ip=yourip
                    url_second_part = response.text
                    return url_fist_part + "&" + url_second_part
        progress(over="apkcombo failed at url: " + url)

    # apkmirror doesn't auto-redirect package name searches so we have to deal with scraping the search page
    # also hosts some patched apps and watch/tv versions that show up as results when searching for the regular app packages, thus the need for user choice
    def apkmirror(found_app_url: str = ""):
        nonlocal url
        base = "https://www.apkmirror.com"
        supported_apps = {
            "com.google.android.youtube": "https://www.apkmirror.com/apk/google-inc/youtube/",
            "com.google.android.apps.youtube.music": "https://www.apkmirror.com/apk/google-inc/youtube-music/",
        }
        if found_app_url:
            supported_apps[package_name] = found_app_url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        }
        if package_name in supported_apps:
            url = supported_apps[package_name]
            if not version:
                progress(5)
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    # this is the first list item and should be the latest version available
                    # /apk/google-inc/youtube/youtube-18-43-45-release/
                    regex = r'<div class="widgetHeader[^"]+">All versions <\/div>.*?<a class="fontBlack" href="([^"]+)'
                    match = re.search(regex, response.text, re.S)
                    if match:
                        url = base + match.group(1)
                    else:
                        progress(
                            over="failed to find the latest version of "
                            + package_name
                            + " on apkmirror"
                        )
                        return
            else:
                slug = re.search(r"(?<=/)[^\/]+(?=\/$)", url).group()
                url = (
                    url
                    + slug
                    + f"-{version.replace('.', '-').replace(':', '')}-release"
                )
            # url should look like this now: https://www.apkmirror.com/apk/google-inc/youtube/youtube-18-43-45-release/
            regex = r'(?<=apkm-badge">APK).*?href="([^"]+)'
            progress(4)
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
                    url = base + re.search(regex, response.text).group(1).replace(
                        "&amp;", "&"
                    )

                    regex = r'<form id="filedownload".*?<\/form>'
                    progress()
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        download_form = re.search(regex, response.text, re.S).group()
                        if download_form:
                            parms = re.findall(
                                r"name=\"([^\"]+)|value=\"([^\"]+)", download_form
                            )
                            parms = list(
                                map(
                                    lambda x: x[0] if parms.index(x) % 2 == 0 else x[1],
                                    parms,
                                )
                            )
                            url = (
                                base
                                + re.search(
                                    r'(?<=action=")([^"]+)', download_form
                                ).group()
                                + "?"
                                + "".join(
                                    [
                                        "&" + value if index % 2 == 0 else "=" + value
                                        for index, value in enumerate(parms)
                                    ]
                                )[1:]
                            )

                            progress()
                            response = requests.get(
                                url, headers=headers, allow_redirects=False
                            )
                            if response.status_code == 302:
                                return response.headers["Location"]
            progress(over="apkmirror failed at url: " + url)
        else:
            url = f'https://www.apkmirror.com/?post_type=app_release&searchtype=app&s="{package_name}"'
            regex = r'<div class="listWidget">.<div class="widgetHeader search-header">.*?<div class="listWidget">'
            progress(5)
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                app_search_result_html = re.search(regex, response.text, re.S).group()
                regex = r'<h5 title="([^"]+).*?href="([^"]+).*?<\/h5>'
                if app_search_result_html:
                    if "No results found matching your query" in app_search_result_html:
                        # print("no results on apkmirror for " + package_name)
                        progress(over="no results on apkmirror for " + package_name)
                        return
                    search_results = re.findall(regex, app_search_result_html, re.S)
                    if search_results:
                        if len(search_results) > 1:
                            filter_function = lambda x: f"{x[0]} : {x[1]}"
                            item = select_item(
                                "Select apkmirror search result (empty for none): ",
                                search_results,
                                filter_function,
                                True,
                            )
                            if item:
                                url = base + item[1]
                                return apkmirror(url)
                            else:
                                return
                        # don't ask if it's just one result
                        url = base + search_results[0][1]
                        # print(f"found apkmirror url for {package_name}: {url}")
                        return apkmirror(url)
            progress(over=f"failed to search for {package_name} on apkmirror")

    # apkpure's downside is that they don't keep many old versions, some revanced recomended versions are pretty old and won't be found here
    def apkpure():
        nonlocal url
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        }

        url = (
            "https://apkpure.com/search/"
            + package_name
            + ("/download" if not version else f"/download/{version}")
        )
        progress(2)
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            regex = r'https://d\.apkpure\.com/b/APK/.*?\?versionCode=\d+.*?(?=")'
            match = re.search(regex, response.text)
            if match:
                url = match.group().replace("&amp;", "&")
                progress()
                response = requests.get(url, headers=headers, allow_redirects=False)
                if response.status_code == 302:
                    url = response.headers["Location"]
                    return url
            progress(
                over="did not find standalone apk for this app/version on apkpure, does it exits? "
                + url
            )
        else:
            progress(over="app not found on apkpure")

    sources = [
        apkcombo,
        apkmirror,
        apkpure,
    ]

    if scan_folder_for_apks:
        # scan script folder, not repo folder inside it
        folder = os.path.dirname(os.getcwd())
        apks = scan_for_apk_files(folder)
        apk = None
        if len(apks) == 1:
            apk = apks[0]
        if len(apks) > 1:
            apk = (
                select_item(
                    "Select apk to use (empty for none): ", apks, allow_empty=True
                )
                or False
            )

        if apk:
            apk = f"../{apk}"
            print("Using user-provided apk file at:", os.path.abspath(apk))
            return apk
        if apk != False:  # if user selected none
            print("No user-provided apk files found in the working directory")

    localversion = []
    if os.path.exists(".apk_version.txt") and os.path.exists(default_apk):
        with open(".apk_version.txt", "r") as file:
            localversion = [file.readline().strip() for _ in range(1)]

    # this is inside get_apk to also allow user-provided apks when using --local
    if local:
        if not localversion:
            print("No local apk file available, downloading...")
        elif package_name not in localversion[0]:
            print(
                f"Warning: Local app ({localversion[0]}) differs from current one ({package_name})"
            )
            fn = lambda x: (
                f"Download {package_name}"
                if x
                else "Patch anyways (only universal patches will apply, if any, and buld name will be wrong)"
            )
            ignore_local = select_item(
                "Your choice (empy for download): ", [True, False], fn, True
            )
            if ignore_local == False:
                return default_apk

    if f"{package_name}-{version}" in localversion:
        print("app.apk is up-to-date")
        return default_apk

    with open(".apk_version.txt", "w") as file:
        pass

    random.shuffle(sources)
    download_link = None
    i = 0
    while download_link == None and i in range(0, len(sources)):
        download_link = sources[i]()
        i += 1
    assert download_link, "Completely failed to download apk"
    download_file(download_link, default_apk)

    with open(".apk_version.txt", "w") as file:
        file.write(f"{package_name}-{version or 'latest'}")

    return default_apk


def select_item(
    message: str, item_list: list, map_function=None, allow_empty: bool = False
):
    printable_item_list = list(map(map_function, item_list)) if map_function else None
    for index, item in enumerate(printable_item_list or item_list, start=1):
        print(f"{index:{len(str(len(item_list)))}}. {item}")

    while True:
        try:
            choice = input(message)
            if choice == "" and allow_empty:
                return None
            choice = int(choice)
            if 1 <= choice <= len(item_list):
                return item_list[choice - 1]
            else:
                print("Please enter a valid number corresponding to the options.")
        except ValueError:
            print("Please enter a valid number.")


def select_multiple_items(
    message: str, item_list: list, map_function=None, allow_empty: bool = False
):
    printable_item_list = list(map(map_function, item_list)) if map_function else None
    for index, item in enumerate(printable_item_list or item_list, start=1):
        print(f"{index:{len(str(len(item_list)))}}. {item}")

    selected_items = []
    while True:
        selection = input(message)
        indices = set()

        try:
            if selection == "" and allow_empty:
                return []
            for part in selection.split(","):
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    indices.update(range(int(start), int(end) + 1))
                else:
                    indices.add(int(part))

            for index in indices:
                if 1 <= index <= len(item_list):
                    selected_items.append(item_list[index - 1])

            return selected_items

        except (ValueError, IndexError):
            print("Invalid input. Please enter valid numbers and/or ranges.")


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
            print(
                "Exiting: Found incompatible java verson, revanced requires at least java 11"
            )
            subprocess.run(cmd)  # show user's java version before exiting
            sys.exit(1)
    except FileNotFoundError:
        print("Exiting: Java not found, install jdk11 or higher")
        sys.exit(1)


def check_keystore_type(keystore_file: str):
    print("Using keystore file:", os.path.abspath(keystore_file), end="")
    command = [
        "keytool",
        "-list",
        "-keystore",
        keystore_file,
        "-storetype",
        "BKS",
        "-provider",
        "org.bouncycastle.jce.provider.BouncyCastleProvider",
        "-providerpath",
        "../bcprov-jdk18on-176.jar",
        "-storepass",
        "",
    ]
    process = subprocess.run(command, capture_output=True, text=True)

    if (
        process.returncode == 1
        and "keytool error: java.lang.Exception: Keystore file does not exist:"
        in process.stdout
    ):
        type = "to_be_generated"
        print(f"\t[{type}]")
        return type

    if process.returncode == 0 and "Your keystore contains 1 entry" in process.stdout:
        if "alias," in process.stdout:
            type = "old"
            print(f"\t[{type}]")
            return type
        if "ReVanced Key," in process.stdout:
            type = "new"
            print(f"\t[{type}]")
            return type

    if (
        process.returncode == 1
        and 'java.lang.Exception: Provider "org.bouncycastle.jce.provider.BouncyCastleProvider" not found'
        in process.stdout
    ):
        print(
            "\nKeycheck failed as BouncyCastle jar file is missing from the working directory"
        )
        return "unexpected"

    print("Unexpected key, patching might fail")
    return "unexpected"


def handleTermux():
    # could import platform and check platform.machine here, and use a different aapt2 file for each architecture
    # https://github.com/ReVanced/revanced-cli/blob/main/docs/0_prerequisites.md
    # problem is i don't have armv7 or x86 devices to test this, so only armv8 is supported for now
    if os.path.exists("aapt2"):
        if not os.access("aapt2", os.X_OK):
            subprocess.run(["chmod", "+x", "aapt2"], capture_output=True)
            if not os.access("aapt2", os.X_OK):
                print(
                    "Can't grant execute permission to aapt2. I don't know why but this can happen if the repo is cloned "
                    + "outside termux root, like inside the download folder. (tested on android 10)"
                )
    else:
        print("aapt2 file is missing, patching will probably fail")


def main():
    default_repo = "revanced"
    default_app = "com.google.android.youtube"
    non_default_app = False
    is_termux = False

    parser = argparse.ArgumentParser(
        description="Build patched apps with ReVanced tools",
        epilog='The script looks for a general "revanced.keystore" file inside the working directory. '
        + "Both pre and past revanced-cli4.0 keys are supported",
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help="build using local files to avoid unnecessary github api requests(max 60/h) and re-downloads",
    )
    parser.add_argument(
        "-e",
        "--export",
        action="store_true",
        help="stop after printing the patch command instead of running it",
    )
    parser.add_argument(
        "repository",
        type=str,
        default=default_repo,
        nargs="?",
        help="github username to download revanced-cli, patches and integrations form, "
        + "also acts as download folder (default and fallback: %(default)s)",
    )
    parser.add_argument(
        "--cli",
        type=str,
        default=None,
        help="github username to download revanced-cli from (priority over repository)",
    )
    parser.add_argument(
        "--patches",
        type=str,
        default=None,
        help="github username to download revanced-patches from (priority over repository)",
    )
    parser.add_argument(
        "--integrations",
        type=str,
        default=None,
        help="github username to download revanced-integrations from (priority over repository)",
    )
    parser.add_argument(
        "-a",
        "--app",
        "--package",
        nargs="?",
        const="",
        default=default_app,
        help="specify an app to patch or be prompted to choose based on patches (default: %(default)s). "
        + "The script will scan the working directory for apk files before trying to download when this option is used. "
        + "No checks are done with this option, you can provide any apk and use at least the universal patches on it",
    )

    args = parser.parse_args()

    if args.app != default_app:
        non_default_app = True

    if "com.termux" in sys.prefix:
        is_termux = True
        handleTermux()

    check_java()

    for folder in ["_builds", args.repository]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    os.chdir(args.repository)

    if not args.local:
        update_revanced(
            args.repository, default_repo, args.cli, args.patches, args.integrations
        )

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
        args.app = select_item("Select app to patch: ", all_apps)
        print("Working with:", args.app)

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
                    print(
                        f'Presuming recomended {"app" if non_default_app else "youtube"} version: {recomended_version}'
                    )

    print('"(-)" prefix means not used by default')
    filter_function = lambda x: (
        f'{x["name"]} - {x["description"]}'
        if x["use"]
        else f'(-) {x["name"]} - {x["description"]}'
    )
    selected_options = select_multiple_items(
        "Select patches (e.g. 4,7-12,1) or empty for default: ",
        app_patches,
        filter_function,
        True,
    )

    command_patches = []
    if selected_options:
        choices = [
            "Only include the selected patches",
            "Exclude the selected patches (from the default ones)",
            "Include selected patches (together with default ones)",
        ]
        selected_item = choices.index(
            select_item("Enter the number of your choice: ", choices)
        )

        if selected_item == 0:
            command_patches.append("--exclusive")
            for patch in selected_options:
                command_patches.append(f'--include={patch["name"]}')
        elif selected_item == 1:
            for patch in selected_options:
                command_patches.append(f'--exclude={patch["name"]}')
        else:
            for patch in selected_options:
                command_patches.append(f'--include={patch["name"]}')

    keystore_file = (
        "../revanced.keystore"
        if os.path.exists(
            os.path.join(os.path.dirname(os.getcwd()), "revanced.keystore")
        )
        else "revanced.keystore"
    )
    output_file = (
        # f'../_builds/revanced({args.repository})[{args.app.replace(".", "_")}].apk'
        f'revanced({args.repository})[{args.app.replace(".", "_")}].apk'
    )
    apk_file = get_apk(args.app, recomended_version, args.local, non_default_app)
    base_command = [
        "java",
        "-jar",
        "cli.jar",
        "patch",
        "--options=options.json",
        # "--resource-cache=.cache", # seems like this can't just be set to a path, it wants a folder with cache already in it. move output file to _builds for now
        "--patch-bundle=patches.jar",
        "--merge=integrations.apk",
        f"--keystore={keystore_file}",
        f"--out={output_file}",
        apk_file,
    ]

    # cli 4.0 doesn't work with old keys
    # https://github.com/ReVanced/revanced-cli/issues/277
    # https://github.com/ReVanced/revanced-cli/issues/272

    # we are in a situation where revanced-cli only works with new keys and inotia00's fork only works with old keys.....
    compatibility_patch_old_key = [
        "--alias=alias",
        "--keystore-entry-password=ReVanced",
        "--keystore-password=ReVanced",
    ]
    compatibility_patch_new_key = [
        "--alias=ReVanced Key",
        "--keystore-entry-password=",
        "--keystore-password=",
    ]

    key_type = check_keystore_type(keystore_file)
    if key_type == "old":
        base_command += compatibility_patch_old_key
    if key_type == "new":
        base_command += compatibility_patch_new_key

    if is_termux:
        base_command += ["--custom-aapt2-binary=../aapt2"]

    base_command += command_patches

    # quotes around patch names that contain spaces
    printable_command = [
        (
            f'{item.split("=")[0]}="{item.split("=")[1]}"'
            if " " in item and "=" in item and item.startswith("--")
            else item
        )
        for item in base_command
    ]
    # for user-provided apks that have spaces
    printable_command = [
        f'"{item}"' if " " in item and not item.startswith("--") else item
        for item in printable_command
    ]
    # add empty quotes to possibly blank arguments like keystore-password
    printable_command = [
        f'{item.split("=")[0]}=""' if re.match(r".*=$", item) else item
        for item in printable_command
    ]
    print("Running:", " ".join(printable_command))

    if not args.export:
        subprocess.run(base_command)
        print('Moved to', os.path.abspath(shutil.move(output_file, '../_builds/' + output_file)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nThe script was interrupted by the user.")
