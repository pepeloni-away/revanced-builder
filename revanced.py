import argparse
import os
import subprocess
import shutil
import json
import time
import re
import sys
import traceback
from random import shuffle
from math import ceil
import urllib.request
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"
)
p = print


def select_one_item(
    message: str, item_list: list, map_function=None, allow_empty: bool = False
):
    printable_item_list = list(map(map_function, item_list)) if map_function else None
    longest_line = 0
    for index, item in enumerate(printable_item_list or item_list, start=1):
        s = f"{index:{len(str(len(item_list)))}}. {item}"
        if len(s) > longest_line:
            longest_line = len(s)
    print(("-" * longest_line)[0 : os.get_terminal_size().columns - 1])
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
    message: str,
    item_list: list,
    map_function=None,
    allow_empty: bool = False,
    custom_input_parser=None,
):
    printable_item_list = list(map(map_function, item_list)) if map_function else None
    longest_line = 0
    for index, item in enumerate(printable_item_list or item_list, start=1):
        s = f"{index:{len(str(len(item_list)))}}. {item}"
        if len(s) > longest_line:
            longest_line = len(s)
    print(("-" * longest_line)[0 : os.get_terminal_size().columns - 1])
    for index, item in enumerate(printable_item_list or item_list, start=1):
        print(f"{index:{len(str(len(item_list)))}}. {item}")

    if custom_input_parser:
        return custom_input_parser(message, allow_empty, item_list)
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


def download_file(url: str, name: str):
    print("Downloading", url, "as", name)
    with urllib.request.urlopen(url) as response:
        total_size = int(response.headers.get("content-length", 0))
        downloaded_bytes = 0

        with open(name, "wb") as file:
            while True:
                chunk = response.read(1024)

                if not chunk:
                    break

                file.write(chunk)
                downloaded_bytes += len(chunk)
                predefined_space = 12 + 16
                predefined_space += len(str(ceil(downloaded_bytes)))

                if total_size:
                    predefined_space += len(str(ceil(total_size)))
                    progress_percent = (downloaded_bytes / total_size) * 100

                    max_length = shutil.get_terminal_size()[0] - predefined_space
                    progress = "#" * int(progress_percent / 100 * max_length)
                    empty = " " * (max_length - len(progress))

                    # 8 fixed characters here, 4 square brackets, 1 space, 1 percent sign, 2 percent digits
                    print(
                        f"\r[{progress}{empty}] [{downloaded_bytes} / {total_size} bytes] [{int(progress_percent)}%]",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\r[{downloaded_bytes} / unknown bytes] [?%]",
                        end="",
                        flush=True,
                    )
        print()


# check for a token in a file to extend rate limit? https://stackoverflow.com/questions/13394077/is-there-a-way-to-increase-the-api-rate-limit-or-to-bypass-it-altogether-for-git
def get_github_releases(
    github_user="revanced",
    cli_repo="revanced-cli",
    patches_repo="revanced-patches",
    integrations_repo="revanced-integrations",
    get: list = ["cli", "patches"],
    amount=1,
    latest=False,
) -> dict:
    # print('arguments:', locals())

    # to be used as fallback when github_user only has their version of revanced-patches for example
    # fallback_github_user = "revanced"

    # cli_repo can have 2 forms: <reponame> and <user/reponame>
    cli_url_path = "/".join(([github_user] + cli_repo.split("/"))[-2:])
    patches_url_path = "/".join(([github_user] + patches_repo.split("/"))[-2:])
    integrations_url_path = "/".join(
        ([github_user] + integrations_repo.split("/"))[-2:]
    )

    slug = "/latest" if latest and amount == 1 else "?per_page=100"

    url_map = {
        "cli": f"https://api.github.com/repos/{cli_url_path}/releases{slug}",
        "patches": f"https://api.github.com/repos/{patches_url_path}/releases{slug}",
        "integrations": f"https://api.github.com/repos/{integrations_url_path}/releases{slug}",
    }

    def request_json(url: str, target: int, last_response_json=None) -> list:
        if last_response_json is None:
            # python doesn't renew it every invocation if last_response_json parameter is set to empty array
            last_response_json = []
        # https://docs.python.org/3/library/urllib.request.html#module-urllib.response
        # https://docs.python.org/3/library/email.message.html#email.message.EmailMessage.get_content_charset
        print("getting", url)
        with urllib.request.urlopen(url) as response:
            content = response.read()
            headers = response.headers
            encoding = headers.get_content_charset()
            decoded = json.loads(content.decode(encoding))

            # put the /latest response in a list for consistency
            if type(decoded) == dict:
                decoded = [decoded]

            last_response_json.extend(decoded)
            response_json = last_response_json

            requests_ratelimit = headers.get("X-RateLimit-Limit")
            requests_remaining = headers.get("X-RateLimit-Remaining")
            requests_used = headers.get("X-RateLimit-Used")
            ratelimit_reset_epoch = int(headers.get("X-RateLimit-Reset"))
            ratelimit_reset_formatted_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(ratelimit_reset_epoch)
            )
            int(requests_used) / int(requests_ratelimit) >= 0.85 and print(
                f"Used {requests_used} out of {requests_ratelimit} github requests. {requests_remaining} remaining. Resets at: {ratelimit_reset_formatted_time}."
            )

            # should make this wait until reset if we hit ratelimit
            # round(time.time()) - ratelimit_reset_epoch

            link_header = headers.get("Link")
            page = {}
            if link_header:
                # turn the link header string into a dict
                a = [s.strip() for s in link_header.split(",")]
                b = [s.strip() for list in [s.split(";") for s in a] for s in list]
                c = {b.pop(1)[5:-1]: b.pop(0)[1:-1] for i in range(int(len(b) / 2))}
                page = c

            if "next" in page:
                if target == 0 or len(response_json) < target:
                    return request_json(
                        page["next"],
                        target,
                        last_response_json=response_json,
                    )

            return response_json if target == 0 else response_json[0:target]

    response = {}
    for x in get:
        response[x] = request_json(url_map[x], amount)
    return response


# nice urllib guide https://devdocs.io/python~3.10/howto/urllib2#urllib-howto
def apkcombo(package_name: str, version: str = "") -> str:
    print = lambda *args: p("apkcombo:", *args)

    # this is either 404 or redirects to the app page with the latest version or the specified version
    # will also redirect to a /old-versions/ app page if specified version is not available (anymore)
    url = (
        "https://apkcombo.com/search/"
        + package_name
        + "/download/"
        + ("apk" if not version else f"phone-{version}-apk")
    )

    print("requesting", url)
    r = Request(url=url, headers={"Referer": "https://apkcombo.com/"})
    try:
        response = urlopen(r)
    except HTTPError as e:
        if e.code == 404:
            print("package not found")
            raise e
        else:
            raise e
    else:
        if response.url.endswith("/old-versions/"):
            msg = "version %s not found, likely too old" % version
            print(msg)
            raise RuntimeError(msg)

        content = response.read()
        headers = response.headers
        encoding = headers.get_content_charset()
        decoded = content.decode(encoding)

        # https://download.apkcombo.com/com.google.android.youtube/YouTube_18.43.41_apkcombo.com.apk?ecp=Y29tLmdvb2dsZS5hbmRyb2lkLnlvdXR1YmUvMTguNDMuNDEvMTU0MDg4NTk1Mi41ODU3M2FmOGFhY2U5YjAxZmY0NTQwMDFhNGI4NDM2MzVhNGM0YjNhLmFwaw==&iat=1699141714&sig=a4201aefd1136aaf098d1d5333988fa3&size=131564206&from=cf&version=old&lang=en
        regex = r'(?<=a href=")https://download\.apkcombo\.com/.*\.apk\?[^"]+'
        # for /r2?u=https..... external download links?, found at least on com.zhiliaoapp.musically, guardian tales
        regex2 = r'(?<=a href=")/r2.*\.apk[^"]+'
        url_fist_part = re.search(regex, decoded) or re.search(regex2, decoded)

        if url_fist_part == None:
            msg = "did not find standalone apk"
            print(msg)
            raise RuntimeError(msg)

        url_fist_part = url_fist_part.group()
        if not url_fist_part.startswith("http"):
            url_fist_part = "https://apkcombo.com" + url_fist_part

        with urlopen(Request("https://apkcombo.com/checkin")) as response:
            content = response.read()
            headers = response.headers
            encoding = headers.get_content_charset()
            # fp=e1aa154442d600ccbfa78e01a042344e&ip=yourip
            decoded = content.decode(encoding)
            return url_fist_part + "&" + decoded


def apkmirror(package_name: str, version: str = "") -> str:
    print = lambda *args: p("apkmirror:", *args)

    # there's no redirect by package name on apkmirror, we scrape the serach page
    # still, there are some package names that aren't unique, like https://www.apkmirror.com/?post_type=app_release&searchtype=app&s=%22com.google.android.youtube%22
    # and https://www.apkmirror.com/?post_type=app_release&searchtype=app&s=%22com.google.android.apps.youtube.music%22
    # so user confirmation will be needed sometimes
    url = f"https://www.apkmirror.com/?post_type=app_release&searchtype=app&s=%22{package_name}%22"
    base_url = "https://www.apkmirror.com"

    headers = {
        "User-Agent": USER_AGENT,
    }

    print("requesting", url)
    r = Request(url=url, headers=headers)
    response = urlopen(r)
    content = response.read()
    response_headers = response.headers
    encoding = response_headers.get_content_charset()
    decoded = content.decode(encoding)

    results_regex = re.compile(
        "(?<=<!-- Nav tabs -->).*?(?=<!-- #primary -->)", flags=re.S
    )
    results = re.search(results_regex, decoded).group()
    # should crash at .group() above if regex gets outdated
    app_url_regex = r'(?<=fontBlack" href=")[^"]+'
    possible_apps = re.findall(app_url_regex, results)
    if not possible_apps:
        msg = "no search results detected"
        print(msg)
        raise RuntimeError(msg)
    print("detected %d search results" % len(possible_apps))
    # possible_apps = [base_url + i for i in possible_apps]
    app = (
        possible_apps[0]
        if len(possible_apps) == 1
        else select_one_item("Pick app: ", possible_apps)
    )

    url = base_url + app
    print("requesting", url)
    r = Request(url=url, headers=headers)
    response = urlopen(r)
    content = response.read()
    response_headers = response.headers
    encoding = response_headers.get_content_charset()
    decoded = content.decode(encoding)

    all_releases_regex = re.compile("All versions(.*?)See more uploads", flags=re.S)
    releases = re.search(all_releases_regex, decoded).group(1)
    latest_release_regex = r'(?<=class="fontBlack" href=")[^"]+'
    url = latest_release_url = (
        base_url + re.search(latest_release_regex, releases).group()
    )

    if version:
        version = version.replace(".", "-")
        version_from_url = re.search(
            r"(?<=-)[\d|-]+(?=-release)", latest_release_url
        ).group()
        url = url.replace(version_from_url, version)

    print("requesting", url)
    # this will 404 if version is not found
    r = Request(url=url, headers=headers)
    response = urlopen(r)
    content = response.read()
    response_headers = response.headers
    encoding = response_headers.get_content_charset()
    decoded = content.decode(encoding)

    # downloads_regex = re.compile(
    #     '<h3 class="addpadding tabs-header ".*?<div class="listWidget', flags=re.S
    # )
    # downloads = re.search(downloads_regex, decoded).group()
    # stated_amount_of_downloads = re.search(r"we currently have (\d+)", decoded).group(1)

    # this regex seems to work well on the full response without filtering downloads first
    variants_regex = re.compile(
        '(?<!table topmargin variants-table">\n {16})<div class="table-row headerFont">.*?href="([^"]+).*?span class="apkm-badge[^>]+>([a-zA-Z0-9_]+)</span>.*?href="[^#]+#disqus_thread".*?</div>\n((?: +<div class="table-cell rowheight addseparator expand pad dowrap">[^<]+</div>\n)+)',
        flags=re.S,
    )
    # variants = re.findall(variants_regex, downloads)
    variants = re.findall(variants_regex, decoded)
    variants = [(i[0], i[1], re.findall(r'dowrap">([^<]+)<', i[2])) for i in variants]
    # variants is a list of tuples like ('/apk/google-inc/youtube-music/youtube-music-7-33-51-release/youtube-music-7-33-51-android-apk-download/', 'APK', ['armeabi-v7a', 'Android 8.0+', 'nodpi']
    # print(variants)
    variants = [i for i in variants if i[1] == "APK"]
    variants = [i for i in variants if i[2][0] in ["arm64-v8a", "universal"]]
    assert len(variants) > 0, "no variants found"
    # print(variants)

    variant = (
        variants[0]
        if len(variants) == 1
        else select_one_item("Pick variant: ", variants)
    )
    url = base_url + variant[0]
    print("requesting", url)
    r = Request(url=url, headers=headers)
    response = urlopen(r)
    content = response.read()
    response_headers = response.headers
    encoding = response_headers.get_content_charset()
    decoded = content.decode(encoding)

    regex = r'(?<=href=")\/apk\/.*?\?key=\w+[^"]+'
    url = base_url + re.search(regex, decoded).group()
    print("requesting", url)
    r = Request(url=url, headers=headers)
    response = urlopen(r)
    content = response.read()
    response_headers = response.headers
    encoding = response_headers.get_content_charset()
    decoded = content.decode(encoding)

    regex = r'<a id="download-link"(?: [a-zA-Z0-9_-]+="[^"]+")+ href="([^"]+)"'
    url = base_url + re.search(regex, decoded).group(1)

    class NoRedirectHandler(HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):
            # raise Exception(f"Redirect detected: {headers.get('Location')}")
            x = Exception("redirect detected")
            x.location = headers.get("Location")
            raise x

    print("requesting", url)
    opener = build_opener(NoRedirectHandler())
    r = Request(url=url, headers=headers)
    try:
        with opener.open(r) as response:
            pass
    except Exception as e:
        url = e.location
        print(url)
        return url


def apkpure(package_name: str, version: str = "") -> str:
    print = lambda *args: p("apkpure:", *args)

    # can also format links like this if needed in the future https://apkpure.com/-/com.google.android.youtube
    url = (
        "https://apkpure.com/search/"
        + package_name
        + ("/download" if not version else f"/download/{version}")
    )
    headers = {
        "User-Agent": USER_AGENT,
    }

    print("requesting", url)
    r = Request(url=url, headers=headers)
    try:
        response = urlopen(r)
    except HTTPError as e:
        if e.code == 404:
            print("package not found")
            raise e
        else:
            raise e

    else:
        if response.url.__contains__("/apk-downloader"):
            msg = "version %s not found, likely too old" % version
            print(msg)
            raise RuntimeError(msg)

        content = response.read()
        response_headers = response.headers
        encoding = response_headers.get_content_charset()
        decoded = content.decode(encoding)

        regex = r'https://d\.apkpure\.com/b/APK/.*?\?versionCode=\d+.*?(?=")'
        url = re.search(regex, decoded)
        if url == None:
            msg = "did not find standalone apk"
            print(msg)
            raise RuntimeError(msg)
        url = url.group()  # .replace("&amp;", "&")

        class NoRedirectHandler(HTTPRedirectHandler):
            def http_error_302(self, req, fp, code, msg, headers):
                # raise Exception(f"Redirect detected: {headers.get('Location')}")
                x = Exception("redirect detected")
                x.location = headers.get("Location")
                raise x

        print("requesting", url)
        opener = build_opener(NoRedirectHandler())
        r = Request(url=url, headers=headers)
        try:
            with opener.open(r) as response:
                pass
        except Exception as e:
            url = e.location
            return url


APK_SOURCES = [
    apkcombo,
    apkmirror,
    apkpure,
]


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "repository",
        default="revanced",
        nargs="?",
        help=(
            "local working directory and github user to download revanced-cli, revanced-patches, and optionally revanced-integrations from."
        ),
    )
    parser.add_argument(
        "-l",
        "--local",
        action="store_true",
        help=("run with the revanced tools available in the working directory"),
    )
    parser.add_argument(
        "-s",
        "--apk_source",
        choices=[x.__name__ for x in APK_SOURCES],
        help="choose where to source apks from, or let the script try all of them in random order until it succeeds",
    )
    revanced_tools_args = parser.add_argument_group(
        "revanced tools",
        description=(
            "arguments in this group can also have the form of <github username/repository name> and can be used to "
            "mix revanced tools from different sources. "
            "example: revanced.py --patches=YT-Advanced/ReX-patches"
        ),
    )
    revanced_tools_args.add_argument("--cli", default="revanced-cli", help="-")
    revanced_tools_args.add_argument("--patches", default="revanced-patches", help="-")
    revanced_tools_args.add_argument(
        "--integrations", default="revanced-integrations", help="-"
    )

    # put these in a selection group?
    parser.add_argument(
        "-sc",
        "--select_cli",
        nargs="?",
        type=int,
        help="as a flag - select from the latest %(const)s (pre)releases, or pass an amount yourself, 0 for all",
        const="50",
    )
    parser.add_argument(
        "-sp",
        "--select_patches",
        nargs="?",
        type=int,
        help="as a flag - select from the latest %(const)s (pre)releases, or pass an amount yourself, 0 for all",
        const="50",
    )

    keystore_args = parser.add_argument_group(
        "keystore",
        description=(
            "arguments in this group are meant for custom keys, they should not be used if you have a normal key generated by revanced. "
            "You can put your revanced keystore file in the root folder (next to revanced.py) and it will be "
            "used to sign all builds. Old keys (from before revanced-cli 4.0) are also supported."
        ),
    )
    keystore_args.add_argument(
        "--keystore",
        nargs="?",
        help="path to a keystore file",
    )
    keystore_args.add_argument(
        "--keystore-password",
        nargs="?",
        help="password for the keystore file",
    )
    keystore_args.add_argument(
        "--keystore-entry-alias", nargs="?", help="name of the keystore entry"
    )
    keystore_args.add_argument(
        "--keystore-entry-password", nargs="?", help="password for the keystore entry"
    )

    args = parser.parse_args()
    # print(args)

    for folder in ["_builds", args.repository]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    os.chdir(args.repository)

    cmd = ["java", "-version"]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        first_line = output.split("\n")[0]
        regex = r"^\w+ version \"?(\d{1,2})"
        version = int(re.match(regex, first_line).group(1))
        if version < 11:
            print("Incompatible java verson, revanced requires at least java 11")
            subprocess.run(cmd)  # show user's java version before exiting
            sys.exit(1)
    except FileNotFoundError:
        sys.exit("Java not found, install jdk11 or higher")

    if not args.local:
        cli = get_github_releases(
            github_user=args.repository,
            cli_repo=args.cli,
            get=["cli"],
            amount=args.select_cli if type(args.select_cli) == int else 1,
            latest=not args.select_cli,
        )
        cli = cli["cli"]
        if args.select_cli == 0 or args.select_cli:
            cli = select_one_item("Select cli version: ", cli, lambda x: x["name"])
        else:
            cli = cli[0]

        patches = get_github_releases(
            github_user=args.repository,
            patches_repo=args.patches,
            get=["patches"],
            amount=args.select_patches if type(args.select_patches) == int else 1,
            latest=not args.select_patches,
        )
        patches = patches["patches"]
        if args.select_patches == 0 or args.select_cli:
            patches = select_one_item(
                "Select patches version: ", patches, lambda x: x["name"]
            )
        else:
            patches = patches[0]

        cli_url = next(
            (
                x["browser_download_url"]
                for x in cli["assets"]
                if x["content_type"] == "application/java-archive"
            ),
            None,
        )
        download_file(cli_url, "cli.jar")

        try:
            patches_url = next(
                (
                    x["browser_download_url"]
                    for x in patches["assets"]
                    if x["name"].endswith(".rvp")
                ),
                None,
            )
        except TypeError as e:
            print("failed to detect patches file")
            print(
                "patches older than v5.0.0 (that use .jar extension) are not supported (yet?)"
            )
            choice = select_one_item(
                "select patches manually: ", patches["assets"], lambda x: x["name"]
            )
            patches_url = choice["browser_download_url"]
        download_file(patches_url, "patches.rvp")

    cmd = [
        "java",
        "-jar",
        "cli.jar",
        "list-patches",
        "patches.rvp",
        "-p",
    ]
    output = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    parsed_patches = output.stdout.strip().split("\n\n")
    parsed_patches[0] = parsed_patches[0].replace("INFO: ", "", 1)
    parsed_patches = [i.split("\n") for i in parsed_patches]
    parsed_patches = list(
        map(lambda x: [list(i.split(":", 1)) for i in x], parsed_patches)
    )
    for list_list in parsed_patches:
        for _list in list_list:
            _list[0] = _list[0].strip().replace(" ", "_").lower()
            _list[1] = _list[1].strip()
            if _list[1] == "true":
                _list[1] = True
            if _list[1] == "false":
                _list[1] = False
            if _list[1] == "null":
                _list[1] = None
            if _list[0] == "index":
                _list[1] = int(_list[1])
    parsed_patches = [dict(x) for x in parsed_patches]
    for _dict in parsed_patches:
        if "compatible_packages" in _dict.keys():
            _dict["compatible_packages"] = _dict["package_name"]
            del _dict["package_name"]

    all_apps = []
    for patch in parsed_patches:
        if "compatible_packages" in patch.keys():
            package = patch["compatible_packages"]
            if package not in all_apps:
                all_apps.append(package)

    # print(all_apps)
    app = select_one_item("Select app: ", all_apps)
    print("Selected", app)
    cmd = ["java", "-jar", "cli.jar", "list-versions", "patches.rvp", f"-f={app}"]
    output = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    versions = list(filter(lambda x: x.startswith("\t"), output.stdout.split("\n")))
    versions = list(map(lambda x: x[1:], versions))
    if len(versions) == 1 and versions[0] == "Any":
        version = ""
    else:
        versions = [v.split(" ", 1) for v in versions]
        versions_patches_dict = dict(versions)
        versions = [v[0] for v in versions]
        versions.sort(reverse=True)
        version = versions[0]
        print("Determined %s as latest supported version" % version)

    app_patches = []
    for patch in parsed_patches:
        # universal patch
        if "compatible_packages" not in patch.keys():
            app_patches.append(patch)
            continue
        if app in patch["compatible_packages"]:
            app_patches.append(patch)
    filter_function = lambda x: (
        f'{x["name"]} - {x["description"]}'
        if x["enabled"]
        else f'(-) {x["name"]} - {x["description"]}'
    )

    def custom_parser(msg, allow_empty, item_list):
        class CustomException(Exception):
            def __init__(self, msg):
                self.msg = msg
                # print( 'custom exception occurred')

        while True:
            selection = input(msg)
            msg = msg.split("\n")[-1]
            try:
                if selection == "" and allow_empty:
                    # return [patch for patch in item_list if patch["enabled"]]
                    return []
                    # return None
                if selection.startswith("e"):
                    selection = selection[1:]
                    if "e" in selection:
                        raise CustomException(
                            "You can only make one exclusive selection!"
                        )
                    t = ["--exclusive"]
                    for part in selection.split(","):
                        part.strip()
                        if part.startswith("+") or part.startswith("-"):
                            raise CustomException(
                                "You can't use + and - in exclusive selection!"
                            )
                        if part.startswith("0"):
                            raise CustomException("The list starts at 1 not 0!")
                        if "-" in part:
                            start, end = map(int, part.split("-"))
                            if end > len(item_list):
                                raise CustomException(
                                    "%d is outside of the list index!" % end
                                )
                            # t += item_list[start - 1:end]
                            t += ["--ei=%s" % i["index"] for i in item_list][
                                start - 1 : end
                            ]
                        else:
                            if int(part) > len(item_list):
                                raise CustomException(
                                    "%d is outside of the list index!" % int(part)
                                )
                            t.append(
                                ["--ei=%s" % i["index"] for i in item_list][
                                    int(part) - 1
                                ]
                            )
                    return t
                else:
                    if "e" in selection:
                        raise CustomException(
                            "e can only be at the beginning of the selection!"
                        )
                    t = []
                    for part in selection.split(","):
                        part.strip()
                        if part[0] not in ["+", "-"]:
                            raise CustomException("Invalid selection.")
                        if part.startswith("-"):
                            part = part[1:]
                            if part.startswith("0"):
                                raise CustomException("The list starts at 1 not 0!")
                            if "-" in part:
                                start, end = map(int, part.split("-"))
                                if end > len(item_list):
                                    raise CustomException(
                                        "%d is outside of the list index!" % end
                                    )
                                t += ["--di=%s" % i["index"] for i in item_list][
                                    start - 1 : end
                                ]
                            else:
                                if int(part) > len(item_list):
                                    raise CustomException(
                                        "%d is outside of the list index!" % int(part)
                                    )
                                t.append(
                                    ["--di=%s" % i["index"] for i in item_list][
                                        int(part) - 1
                                    ]
                                )
                            # return t
                        if part.startswith("+"):
                            part = part[1:]
                            if part.startswith("0"):
                                raise CustomException("The list starts at 1 not 0!")
                            if "-" in part:
                                start, end = map(int, part.split("-"))
                                if end > len(item_list):
                                    raise CustomException(
                                        "%d is outside of the list index!" % end
                                    )
                                t += ["--ei=%s" % i["index"] for i in item_list][
                                    start - 1 : end
                                ]
                            else:
                                if int(part) > len(item_list):
                                    raise CustomException(
                                        "%d is outside of the list index!" % int(part)
                                    )
                                t.append(
                                    ["--ei=%s" % i["index"] for i in item_list][
                                        int(part) - 1
                                    ]
                                )
                            # return t
                    return t
            except CustomException as e:
                print(e)
            except Exception as e:
                print(e)

    selected_patches = select_multiple_items(
        (
            '"(-)" prefix means not used by default.\n'
            "Select patches with id or range (e.g. 4,7-12,1).\n"
            "Enable or disable selections by prefixing with + and - (e.g. +4,-6-12).\n"
            "Make one exclusive selection by prefixing it with e (e.g. e1,4,7-22,5).\n"
            "Enter selection or leave empty for default: "
        ),
        app_patches,
        filter_function,
        True,
        custom_parser,
    )
    # print(selected_patches)

    apk_sources = (
        [source for source in APK_SOURCES if source.__name__ == args.apk_source]
        if args.apk_source
        else APK_SOURCES
    )
    shuffle(apk_sources)
    apk_url = None
    while apk_url == None and len(apk_sources):
        try:
            apk_url = apk_sources.pop()(package_name=app, version=version)
        except Exception as e:
            tb = traceback.format_exc()
            print("\tfailed", e, "\n", tb, "\n")
    assert apk_url, "Failed to scrape apk url."
    download_file(apk_url, "apk.apk")

    keystore_file = (
        args.keystore
        if args.keystore
        else (
            "../revanced.keystore"
            if os.path.exists(
                os.path.join(os.path.dirname(os.getcwd()), "revanced.keystore")
            )
            else "revanced.keystore"
        )
    )
    output_file = f'revanced({args.repository})[{app.replace(".", "_")}].apk'

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

        if (
            process.returncode == 0
            and "Your keystore contains 1 entry" in process.stdout
        ):
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

    keystore_options_map = {
        "old": {
            "--keystore-password": "ReVanced",
            "--keystore-entry-alias": "alias",
            "--keystore-entry-password": "ReVanced",
        },
        "new": {
            "--keystore-password": "",
            "--keystore-entry-alias": "ReVanced Key",
            "--keystore-entry-password": "",
        },
    }
    keystore_type = check_keystore_type(keystore_file)
    keystore_options = []
    if keystore_type in keystore_options_map.keys():
        for key, val in keystore_options_map[keystore_type].items():
            keystore_options.append(f"{key}={val}")
    else:
        for key in [
            "keystore-password",
            "keystore-entry-alias",
            "keystore-entry-password",
        ]:
            if key in args:
                keystore_options.append(f"--{key}={args.key}")

    build_command = [
        "java",
        "-jar",
        "cli.jar",
        "patch",
        "-p=patches.rvp",
        *selected_patches,
        "--keystore=%s" % keystore_file,
        *keystore_options,
        "--out=%s" % output_file,
        "apk.apk",
    ]

    if "com.termux" in sys.prefix:
        if os.path.exists("../aapt2"):
            build_command.append("--custom-aapt2-binary=../aapt2")
            if not os.access("../aapt2", os.X_OK):
                subprocess.run(["chmod", "+x", "../aapt2"], capture_output=True)
                if not os.access("../aapt2", os.X_OK):
                    print(
                        "aapt2 file is not executable and execute permission can't be added. Try cloning the repo somewhere inside termux "
                        "without using the /storage path."
                    )
        else:
            print("aapt2 file is missing, patching will probably fail")

    # print(build_command)
    subprocess.run(build_command)
    print(
        "Moved to",
        os.path.abspath(shutil.move(output_file, "../_builds/" + output_file)),
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("user interrupt")
