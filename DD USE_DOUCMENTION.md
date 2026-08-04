# Downloader Use Documentation

This folder contains the downloader script:

- [download_testpoint_pages.py](D:\clean praser\downloader\download_testpoint_pages.py)

## What This Script Does

The script downloads TestPointPK HTML pages and saves them into a folder named from the URL slug.

It can handle:

- one page URL
- page ranges
- multiple URLs
- a text file with URLs

It also:

- creates a `logs` folder
- writes progress into `logs.txt`
- shows live progress in terminal
- retries failed pages 3 times
- writes failed URLs into `UNFECTEDOR PRASE.TXT`

## Example For Page Range

```powershell
python "D:\clean praser\downloader\download_testpoint_pages.py" --start-url "https://testpointpk.com/important-mcqs/islamic-studies-mcqs?page=2" --end-page 535
```

This will create a folder like:

```text
D:\clean praser\islamic-studies-mcqs
```

Inside it, the script saves:

- downloaded HTML pages
- `logs\logs.txt`
- `UNFECTEDOR PRASE.TXT` if some pages fail after 3 attempts

## Example For One Page

```powershell
python "D:\clean praser\downloader\download_testpoint_pages.py" --start-url "https://testpointpk.com/important-mcqs/psychological-assessment-mcqs"
```

This creates a folder named:

```text
psychological-assessment-mcqs
```

## Example For List Of URLs

```powershell
python "D:\clean praser\downloader\download_testpoint_pages.py" --urls "https://testpointpk.com/important-mcqs/psychological-assessment-mcqs" "https://testpointpk.com/important-mcqs/islamic-studies-mcqs?page=2"
```

## Example For File Of URLs

Create a text file like this:

```text
https://testpointpk.com/important-mcqs/psychological-assessment-mcqs
https://testpointpk.com/important-mcqs/islamic-studies-mcqs?page=2
```

Then run:

```powershell
python "D:\clean praser\downloader\download_testpoint_pages.py" --urls-file "D:\clean praser\my_urls.txt"
```

## Optional Output Folder

If you want all downloaded folders to be created somewhere else, use:

```powershell
python "D:\clean praser\downloader\download_testpoint_pages.py" --start-url "https://testpointpk.com/important-mcqs/psychological-assessment-mcqs" --output-dir "D:\clean praser\imp2"
```

## How Progress Looks

The script prints messages like:

```text
[2026-07-17 20:44:43] [3/11] Fetching page: https://testpointpk.com/important-mcqs/islamic-studies-mcqs?page=3
[2026-07-17 20:44:43] [3/11] Saved HTML: page-0003.html
```

## Important Note

I verified the script syntax and CLI help.

Live downloading was not tested in this environment because network access is restricted here.



https://pakmcqs.com/category/everyday-science-mcqs/page/2





python "D:\clean praser\downloader\download_testpoint_pages.py" --urls-file "D:\clean praser\downloader\PAK MCQS\EVERY DAY SCEICENC\EVERYDAT SCINT URLS.txt"