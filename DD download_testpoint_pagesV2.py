from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


LOGS_DIR_NAME = "logs"
LOG_FILE_NAME = "logs.txt"
UNFETCHED_FILE_NAME = "UNFECTEDOR PRASE.TXT"

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_message(message: str, log_path: Path | None = None) -> None:
    line = f"[{timestamp()}] {message}"

    print(line, flush=True)

    if log_path is not None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def slug_from_url(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    slug = path.split("/")[-1].strip()

    return slug or "downloaded-pages"


def safe_folder_name(name: str) -> str:
    invalid_characters = '<>:"/\\|?*'

    for character in invalid_characters:
        name = name.replace(character, "_")

    name = name.strip().strip(".")

    return name or "downloaded-pages"


def build_log_path(output_dir: Path) -> Path:
    logs_dir = output_dir / LOGS_DIR_NAME
    logs_dir.mkdir(parents=True, exist_ok=True)

    return logs_dir / LOG_FILE_NAME


def build_unfetched_path(output_dir: Path) -> Path:
    return output_dir / UNFETCHED_FILE_NAME


def normalize_url(url: str) -> str:
    return url.strip()


def page_number_from_url(url: str) -> int | None:
    query = dict(
        parse_qsl(
            urlsplit(url).query,
            keep_blank_values=True,
        )
    )

    page_value = query.get("page", "").strip()

    if not page_value:
        return None

    try:
        return int(page_value)
    except ValueError:
        return None


def replace_page(url: str, page_number: int) -> str:
    split_result = urlsplit(url)

    query_pairs = dict(
        parse_qsl(
            split_result.query,
            keep_blank_values=True,
        )
    )

    query_pairs["page"] = str(page_number)

    new_query = urlencode(query_pairs, doseq=True)

    return urlunsplit(
        (
            split_result.scheme,
            split_result.netloc,
            split_result.path,
            new_query,
            split_result.fragment,
        )
    )


def build_range_urls(start_url: str, end_page: int) -> list[str]:
    start_page = page_number_from_url(start_url) or 1

    if end_page < start_page:
        raise ValueError(
            f"End page {end_page} is smaller than start page {start_page}."
        )

    return [
        replace_page(start_url, page_number)
        for page_number in range(start_page, end_page + 1)
    ]


def read_urls_file(urls_file: str) -> list[str]:
    file_path = Path(urls_file)

    if not file_path.exists():
        raise FileNotFoundError(
            f"URLs file was not found: {file_path}"
        )

    lines = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    return [
        normalize_url(line)
        for line in lines
        if line.strip()
        and not line.strip().startswith("#")
    ]


def remove_duplicate_urls(urls: list[str]) -> list[str]:
    unique_urls: list[str] = []
    seen: set[str] = set()

    for url in urls:
        if url and url not in seen:
            unique_urls.append(url)
            seen.add(url)

    return unique_urls


def build_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []

    if args.start_url:
        if args.end_page is not None:
            urls.extend(
                build_range_urls(
                    args.start_url,
                    args.end_page,
                )
            )
        else:
            urls.append(
                normalize_url(args.start_url)
            )

    if args.urls:
        urls.extend(
            normalize_url(url)
            for url in args.urls
        )

    if args.urls_file:
        urls.extend(
            read_urls_file(args.urls_file)
        )

    unique_urls = remove_duplicate_urls(urls)

    if not unique_urls:
        raise ValueError(
            "No URLs provided. Use --start-url, --urls, or --urls-file."
        )

    return unique_urls


def build_output_folder(
    args: argparse.Namespace,
    base_dir: Path,
    urls: list[str],
) -> Path:
    if args.urls_file:
        urls_file_path = Path(args.urls_file)

        # URLS.txt becomes folder URLS
        folder_name = safe_folder_name(
            urls_file_path.stem
        )

    elif args.start_url:
        folder_name = safe_folder_name(
            slug_from_url(args.start_url)
        )

    elif urls:
        folder_name = safe_folder_name(
            slug_from_url(urls[0])
        )

    else:
        folder_name = "downloaded-pages"

    output_dir = base_dir / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


def file_name_from_url(
    url: str,
    fallback_index: int,
) -> str:
    page_number = page_number_from_url(url)

    if page_number is not None:
        return f"page-{page_number:04d}.html"

    return f"page-{fallback_index:04d}.html"


def create_unique_file_name(
    output_dir: Path,
    requested_file_name: str,
) -> str:
    requested_path = output_dir / requested_file_name

    if not requested_path.exists():
        return requested_file_name

    stem = requested_path.stem
    suffix = requested_path.suffix

    counter = 2

    while True:
        new_file_name = f"{stem}-{counter:02d}{suffix}"
        new_path = output_dir / new_file_name

        if not new_path.exists():
            return new_file_name

        counter += 1


def fetch_html(
    url: str,
    timeout: int,
) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        },
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:
        charset = (
            response.headers.get_content_charset()
            or "utf-8"
        )

        return response.read().decode(
            charset,
            errors="ignore",
        )


def save_html(
    output_dir: Path,
    file_name: str,
    html: str,
) -> Path:
    output_path = output_dir / file_name

    output_path.write_text(
        html,
        encoding="utf-8",
    )

    return output_path


def append_unfetched(
    output_dir: Path,
    url: str,
    reason: str,
) -> None:
    unfetched_path = build_unfetched_path(
        output_dir
    )

    with unfetched_path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            f"{url} | {reason}\n"
        )


def fetch_with_retries(
    url: str,
    output_dir: Path,
    log_path: Path,
    timeout: int,
    retries: int,
) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            log_message(
                f"Attempt {attempt}/{retries} for URL: {url}",
                log_path,
            )

            html = fetch_html(
                url,
                timeout,
            )

            if not html.strip():
                raise ValueError(
                    "Empty response body"
                )

            return html

        except (
            HTTPError,
            URLError,
            TimeoutError,
            ValueError,
            OSError,
        ) as error:
            log_message(
                f"Attempt {attempt} failed for {url}: {error}",
                log_path,
            )

            if attempt == retries:
                append_unfetched(
                    output_dir,
                    url,
                    str(error),
                )

                log_message(
                    f"Marked as unfetched: {url}",
                    log_path,
                )

                return None

            time.sleep(1)

    return None


def download_urls(
    urls: list[str],
    output_dir: Path,
    timeout: int,
    retries: int,
) -> None:
    log_path = build_log_path(output_dir)
    unfetched_path = build_unfetched_path(output_dir)

    log_message(
        f"Starting downloader.",
        log_path,
    )

    log_message(
        f"Output folder: {output_dir}",
        log_path,
    )

    log_message(
        f"URLs queued: {len(urls)}",
        log_path,
    )

    log_message(
        f"Unfetched file: {unfetched_path}",
        log_path,
    )

    success_count = 0
    failed_count = 0

    for index, url in enumerate(
        urls,
        start=1,
    ):
        requested_file_name = file_name_from_url(
            url,
            index,
        )

        file_name = create_unique_file_name(
            output_dir,
            requested_file_name,
        )

        log_message(
            f"[{index}/{len(urls)}] Fetching page: {url}",
            log_path,
        )

        html = fetch_with_retries(
            url=url,
            output_dir=output_dir,
            log_path=log_path,
            timeout=timeout,
            retries=retries,
        )

        if html is None:
            failed_count += 1
            continue

        output_path = save_html(
            output_dir,
            file_name,
            html,
        )

        success_count += 1

        log_message(
            f"[{index}/{len(urls)}] Saved HTML: {output_path.name}",
            log_path,
        )

    log_message(
        f"Download completed for folder: {output_dir.name}",
        log_path,
    )

    log_message(
        f"Successful pages: {success_count}",
        log_path,
    )

    log_message(
        f"Failed pages: {failed_count}",
        log_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download TestPointPK pages. "
            "When --urls-file is used, all HTML files are saved "
            "inside a folder named after the URLs text file."
        )
    )

    parser.add_argument(
        "--start-url",
        help="Single URL or the first URL in a page range.",
    )

    parser.add_argument(
        "--end-page",
        type=int,
        help=(
            "Last page number for a paginated range. "
            "Use with --start-url."
        ),
    )

    parser.add_argument(
        "--urls",
        nargs="+",
        help="One or more direct URLs to fetch.",
    )

    parser.add_argument(
        "--urls-file",
        help=(
            "Text file containing one URL per line. "
            "All HTML files will be saved inside a folder "
            "named after this text file."
        ),
    )

    parser.add_argument(
        "--output-dir",
        default=str(Path.cwd()),
        help=(
            "Base folder where the download folder "
            "will be created."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds.",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=(
            "Number of attempts before recording "
            "a URL as unfetched."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        urls = build_urls(args)

        base_dir = Path(
            args.output_dir
        ).resolve()

        base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_dir = build_output_folder(
            args=args,
            base_dir=base_dir,
            urls=urls,
        )

        urls.sort(
            key=lambda url: (
                page_number_from_url(url)
                if page_number_from_url(url) is not None
                else 0
            )
        )

        download_urls(
            urls=urls,
            output_dir=output_dir,
            timeout=args.timeout,
            retries=args.retries,
        )

    except (
        ValueError,
        FileNotFoundError,
        PermissionError,
        OSError,
    ) as error:
        log_message(
            f"ERROR: {error}"
        )

        raise SystemExit(1) from error


if __name__ == "__main__":
    main()