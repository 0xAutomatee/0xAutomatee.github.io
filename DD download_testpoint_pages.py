from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable
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


def build_output_folder(base_dir: Path, url: str) -> Path:
    folder = base_dir / slug_from_url(url)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def build_log_path(output_dir: Path) -> Path:
    logs_dir = output_dir / LOGS_DIR_NAME
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / LOG_FILE_NAME


def build_unfetched_path(output_dir: Path) -> Path:
    return output_dir / UNFETCHED_FILE_NAME


def normalize_url(url: str) -> str:
    return url.strip()


def page_number_from_url(url: str) -> int | None:
    query = dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))
    page_value = query.get("page", "").strip()
    if not page_value:
        return None
    try:
        return int(page_value)
    except ValueError:
        return None


def replace_page(url: str, page_number: int) -> str:
    split_result = urlsplit(url)
    query_pairs = dict(parse_qsl(split_result.query, keep_blank_values=True))
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
        raise ValueError(f"End page {end_page} is smaller than start page {start_page}.")
    return [replace_page(start_url, page_number) for page_number in range(start_page, end_page + 1)]


def build_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []

    if args.start_url:
        if args.end_page is not None:
            urls.extend(build_range_urls(args.start_url, args.end_page))
        else:
            urls.append(normalize_url(args.start_url))

    if args.urls:
        urls.extend(normalize_url(url) for url in args.urls)

    if args.urls_file:
        file_path = Path(args.urls_file)
        lines = file_path.read_text(encoding="utf-8").splitlines()
        urls.extend(normalize_url(line) for line in lines if line.strip())

    unique_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url and url not in seen:
            unique_urls.append(url)
            seen.add(url)

    if not unique_urls:
        raise ValueError("No URLs provided. Use --start-url, --urls, or --urls-file.")

    return unique_urls


def file_name_from_url(url: str, fallback_index: int) -> str:
    page_number = page_number_from_url(url)
    if page_number is not None:
        return f"page-{page_number:04d}.html"
    slug = slug_from_url(url)
    return f"{slug}-{fallback_index:04d}.html"


def fetch_html(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def save_html(output_dir: Path, file_name: str, html: str) -> Path:
    output_path = output_dir / file_name
    output_path.write_text(html, encoding="utf-8")
    return output_path


def append_unfetched(output_dir: Path, url: str, reason: str) -> None:
    unfetched_path = build_unfetched_path(output_dir)
    with unfetched_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{url} | {reason}\n")


def fetch_with_retries(
    url: str,
    output_dir: Path,
    log_path: Path,
    timeout: int,
    retries: int,
) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            log_message(f"Attempt {attempt}/{retries} for URL: {url}", log_path)
            html = fetch_html(url, timeout)
            if not html.strip():
                raise ValueError("Empty response body")
            return html
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
            log_message(f"Attempt {attempt} failed for {url}: {error}", log_path)
            if attempt == retries:
                append_unfetched(output_dir, url, str(error))
                log_message(f"Marked as unfetched: {url}", log_path)
                return None
            time.sleep(1)
    return None


def group_urls_by_slug(urls: Iterable[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for url in urls:
        grouped.setdefault(slug_from_url(url), []).append(url)
    return grouped


def download_group(urls: list[str], base_dir: Path, timeout: int, retries: int) -> None:
    output_dir = build_output_folder(base_dir, urls[0])
    log_path = build_log_path(output_dir)
    unfetched_path = build_unfetched_path(output_dir)

    log_message(f"Starting downloader for folder: {output_dir}", log_path)
    log_message(f"URLs queued: {len(urls)}", log_path)
    log_message(f"Unfetched file: {unfetched_path}", log_path)

    success_count = 0
    failed_count = 0
    for index, url in enumerate(urls, start=1):
        file_name = file_name_from_url(url, index)
        log_message(f"[{index}/{len(urls)}] Fetching page: {url}", log_path)
        html = fetch_with_retries(url, output_dir, log_path, timeout, retries)
        if html is None:
            failed_count += 1
            continue
        output_path = save_html(output_dir, file_name, html)
        success_count += 1
        log_message(f"[{index}/{len(urls)}] Saved HTML: {output_path.name}", log_path)

    log_message(f"Download completed for folder: {output_dir.name}", log_path)
    log_message(f"Successful pages: {success_count}", log_path)
    log_message(f"Failed pages: {failed_count}", log_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download TestPointPK pages into slug-named folders with logs and retry handling."
    )
    parser.add_argument("--start-url", help="Single URL or the first URL in a page range.")
    parser.add_argument(
        "--end-page",
        type=int,
        help="Last page number for a paginated range. Use with --start-url.",
    )
    parser.add_argument("--urls", nargs="+", help="One or more direct URLs to fetch.")
    parser.add_argument("--urls-file", help="Text file containing one URL per line.")
    parser.add_argument(
        "--output-dir",
        default=str(Path.cwd()),
        help="Base folder where slug-named download folders will be created.",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="How many times to retry a failed page before recording it as unfetched.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    urls = build_urls(args)
    base_dir = Path(args.output_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    grouped_urls = group_urls_by_slug(urls)
    for group_slug, group_urls in grouped_urls.items():
        group_urls.sort(key=lambda url: page_number_from_url(url) if page_number_from_url(url) is not None else 0)
        print(f"Preparing folder for slug: {group_slug}", flush=True)
        download_group(group_urls, base_dir, args.timeout, args.retries)


if __name__ == "__main__":
    main()
