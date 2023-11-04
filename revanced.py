import os
import requests
import json
import subprocess
import sys
import re
import argparse

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
            # sys.stdout.write(f"\r[{int(progress_percent)}%] [{'#' * int(progress_percent / 2)}{' ' * (50 - int(progress_percent / 2))}]")
            sys.stdout.write(f"\r[{'#' * int(progress_percent / 2)}{' ' * (50 - int(progress_percent / 2))}] [{int(progress_percent)}%]")
            sys.stdout.flush()
    print()

def update_revanced(repo: str, fallback_repo: str, cli: str, patches: str, integrations: str):
    def get_github_download_links(url, furl=None, furl1=None):
        response = requests.get(url)
        if response.status_code == 200:
            response = response.json()
            links = []
            for item in response["assets"]:
                links.append(item["name"])
                links.append(item["browser_download_url"])
            return links # [name, url, ...]
        else:
            print(f"Failed to get download link from {url}")
            if furl1 and furl != furl1:
                print("Attempting with fallback url")
                return get_github_download_links(furl, furl1)
            elif furl and url != furl:
                print("Attempting with fallback url")
                return get_github_download_links(furl)
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
    if os.path.exists(".versions.txt") and files_still_there():
        with open(".versions.txt", "r") as file:
            localfiles = [file.readline().strip() for _ in range(3)]

    with open(".versions.txt", "w") as file:
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

    with open(".versions.txt", "w") as file:
        file.write(cli_version + "\n")
        file.write(patches_version + "\n")
        file.write(integrations_version)

def get_apk(version: str):
    total_i = 0
    last_progress = ""
    def fail(url: str, level: int=0):
        print("Failed at url" + f" {level}:" if level else ":", url)
        raise Exception("Failed to get apk download link")
    
    def log_version_on_success():
        with open(".youtube_version.txt", "w") as file:
            file.write(version)
    
    def progress(last_progress=last_progress):
        msg = f"Fetching [{i}/{total_i or '?'}]: {url}"
        spaces_to_clear = " " * len(last_progress)
        print(f"\r{spaces_to_clear}", end="", flush=True)
        last_progress = msg
        print(f"\r{msg}", end="", flush=True)
    
    def finish_progress():
        print(f"\r{' ' * len(last_progress)}", end="", flush=True)

    def download_question_mark(url: str):
        if version in localversion:
            print("youtube.apk is up-to-date")
        else:
            download_file(url, 'youtube.apk')

    localversion = []
    if os.path.exists(".youtube_version.txt") and os.path.exists("youtube.apk"):
        with open(".youtube_version.txt", "r") as file:
            localversion = [file.readline().strip() for _ in range(1)]

    with open(".youtube_version.txt", "w") as file:
        pass

    try:
        version_dashes = version.replace(".", "-")
        base = "https://www.apkmirror.com"
        url = f"https://www.apkmirror.com/apk/google-inc/youtube/youtube-{version_dashes}-release/"
        regex = r"(?<=apkm-badge\">APK).*\n.*href=\"([^\"]+)"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        }
        total_i = 4
        i = 1
        progress()
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            url = base + re.findall(regex, response.text)[0]
            regex = r"(?<=href=\")(/apk/google-inc/youtube/.*\?key=\w+[^\"]+)"
            i = 2
            progress()
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                url = base + re.findall(regex, response.text)[0].replace("&amp;", "&")
                regex = r"<form id=\"filedownload\".*<\/form>"
                i = 3
                progress()
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    download_form = re.findall(regex, response.text, flags=re.S)[0]
                    parms = re.findall(r"name=\"([^\"]+)|value=\"([^\"]+)", download_form)
                    parms = list(map(lambda x: x[0] if parms.index(x) % 2 == 0 else x[1], parms))
                    url = (
                        base +
                        re.findall(r"action=\"([^\"]+)", download_form)[0] +
                        "?" +
                        "".join(["&" + value if index % 2 == 0 else "=" + value for index, value in enumerate(parms)])[1:]
                        )
                    i = 4
                    progress()
                    finish_progress()
                    response = requests.get(url, headers=headers, allow_redirects=False)
                    if response.status_code == 302:
                        url = response.headers["Location"]
                        download_question_mark(url)
                        log_version_on_success()
                        return
                    else:
                        fail(url, i)
                else:
                    fail(url, i)
            else:
                fail(url, i)
        else:
            fail(url, i)
    except Exception as e:
        print("Failed to get apk download url from apkmirror\n", e)
        print("Falling back to apkcombo")
    
    # apkcombo is a good source but they shill their own apk installer with xapks as the only option sometimes
    # https://apkcombo.com/youtube/com.google.android.youtube/download/phone-18.38.44-apk case in point, whereas apkmirror provides the normal apk

    url = f"https://apkcombo.com/youtube/com.google.android.youtube/download/phone-{version}-apk"
    checkin_url = "https://apkcombo.com/checkin"
    pattern = r"(?<=a href=\")https://download.apkcombo.com/com.google.android.youtube[^\"]+"
    i = 1
    response = requests.get(checkin_url)
    if response.status_code == 200:
        checkin = response.text
        i = 2
        response = requests.get(url)
        if response.status_code == 200:
            match = re.findall(pattern, response.text)[0]
            apk_url = match + "&" + checkin
            download_question_mark(apk_url)
            log_version_on_success()
        else:
            fail(url, i)
    else:
        fail(checkin_url, i)

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

    if process.returncode == 0 and "Your keystore contains 2 entries" in process.stdout and "alias," in process.stdout and "ReVanced Key," in process. stdout:
        print("Fixed keystore (see -h)")
        return "fixed"

    print("Unexpected key, patching might fail")
    return "unexpected"

def main():
    default_repo = "revanced"

    parser = argparse.ArgumentParser(description="Build patched youtube apks with Revanced tools")
    parser.add_argument("-l", "--local", action="store_true", help="Skip downloads and use the previously downloaded files")
    parser.add_argument("-r", "--repository", type=str, default=default_repo,
                        help="Github repository name for working directory and revanced-cli, patches and integrations (default and fallback: %(default)s)")
    parser.add_argument("--cli", type=str, default=None, help="Github repository name for revanced-cli. Has priority over --repository")
    parser.add_argument("--patches", type=str, default=None, help="Github repository name for revanced-patches. Has priority over --repository")
    parser.add_argument("--integrations", type=str, default=None, help="Github repository name for revanced-integrations. Has priority over --repository")

    args = parser.parse_args()

    check_java()

    for folder in ["_builds", args.repository]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    os.chdir(args.repository)

    if not args.local:
        update_revanced(args.repository, default_repo, args.cli, args.patches, args.integrations)

    youtube_patches = []
    recomended_version = None
    with open("patches.json", "r") as file:
        data = json.load(file)
    for key in data:
        # include universal patches
        if key["compatiblePackages"] == None:
            youtube_patches.append(key)
            continue
        for package in key["compatiblePackages"]:
            if package["name"] == "com.google.android.youtube":
                youtube_patches.append(key)
                # this isn't optimal but so far patches were updated all at once so it works
                if not recomended_version and package["versions"]:
                    recomended_version = package["versions"][-1]
                    print("Presuming recomended youtube version:", recomended_version)
    
    if not args.local:
        get_apk(recomended_version)

    def get_patch_name_and_description(x):
        default_string = f'{x["name"]} - {x["description"]}'
        if x["use"] == False:
            return "(-) " + default_string
        return default_string
    all_options = map(get_patch_name_and_description, youtube_patches)

    for i, item in enumerate(all_options, start=1):
        print(f"{i}. {item}")

    print('"(-)" prefix means excluded by defalut')
    while True:
        try:
            user_input = input("Select patches e.g. 1,4,7,8-12,14 or empty for default: ")
            selected_options = select_options(user_input, youtube_patches)
            break
        except IndexError:
            print("Invalid selection.")

    keystore_file = "../revanced.keystore" if os.path.exists(os.path.join(os.path.dirname(os.getcwd()), "revanced.keystore")) else "revanced.keystore"
    base_command = ["java", "-jar", "cli.jar", "patch", "--patch-bundle=patches.jar", "--merge=integrations.apk", "--keystore=" + keystore_file,
                    f"--out=../_builds/revanced({args.repository}).apk", "youtube.apk"]

    # cli 4.0 doesn't work with old keys
    # https://github.com/ReVanced/revanced-cli/issues/277
    # https://github.com/ReVanced/revanced-cli/issues/272

    # we are in a situation where revanced-cli only works with new keys and inotia00's fork only works with old keys.....
    compatibility_patch_old_key = ["--alias=alias", "--keystore-entry-password=ReVanced", "--keystore-password=ReVanced"]
    compatibility_patch_new_key = ["--alias=ReVanced Key", "--keystore-entry-password=", "--keystore-password="]

    if selected_options:
        user_choice = get_selection_goal()

        if user_choice == 1:
            base_command.append("--exclusive")
            for patch in selected_options:
                base_command.append(f'--include={patch["name"]}')
        elif user_choice == 2:
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
