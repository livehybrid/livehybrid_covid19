# Coronavirus (COVID-19) Data tracker for Splunk

Please note: this is a personal project to demonstrate the ease of pulling data from various sources and is not related to my day job, or any form of official publishing of data/figures.  

This has been tested on Linux and MacOSX Splunk Enterprise 8.0 and can be run on a free 500mb license. Head over to https://www.splunk.com/download to get started for free.  

Clone the directory to $SPLUNK_HOME/etc/apps/livehybrid_covid19 (typically /opt/splunk/etc/apps/livehybrid_covid19).  
To enable all inputs you will need a GitHub API key (https://github.com/settings/tokens) in order to pull the worldwide data using the GitHub API, for UK/US only regions you do not need this.

To enable all inputs create a file: local/inputs.conf containing the following 
```
[covid19://gitimport]
disabled = 0
repo_token = <your_key_from_github.com/settings/tokens>

[covidphe_georegions://arcgis]
disabled = 0

[covidphe_nhsregions://arcgis]
disabled = 0

[covidphe_stats://arcgis]
disabled = 0

[covidcdc_usregions.py://cdc]
disabled = 0
```

By default this data will go to the `main` index, set an index for each input stanza to over-ride this. You will also need to update the `macro.conf` file with the correct index name.
