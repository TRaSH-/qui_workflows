# qui_workflows

Based on the [BZ workflow](https://github.com/BZ00001/qui_workflows): shortened the noHL seeding time to 21 days and added optional pre-information tags

## Series

| Workflows                         | Description                                                                |
| --------------------------------- | -------------------------------------------------------------------------- |
| Delete noHL Tier 1.json           | Delete: noHL Tier 1 - after 21 days, If minimum seeders is 3, keep seeding |
| Delete noHL Tier 2.json           | Delete: noHL Tier 2 - after 21 days                                        |
| Delete noHL Tier 3.json           | Delete: noHL Tier 3 - after 21 days                                        |
| Delete problem cross-seeds.json   | Delete: cross-seed that have issues                                        |
| Delete unregistered torrents.json | Delete: unregistered torrents                                              |
| Tag noHL Tier 1.json              | Tag: noHL Tier 1 with `~Tier1-noHL-21`                                     |
| Tag noHL Tier 2.json              | Tag: noHL Tier 2 with `~Tier2-noHL-21`                                     |
| Tag noHL Tier 3.json              | Tag: noHL Tier 3 with `~Tier3-noHL-21`                                     |
| Tag noHL.json                     | Tag: torrents that are not hardlinked with `noHL`                          |
| Tag Season Pack.json              | Tag: Season Packs with `Season Pack`                                       |
| Tag Single Episodes.json          | Tag: Single Episodes with `Episodes`                                       |
| Tag Tier 1.json                   | Tag: Tier 1 with `tier1`                                                   |
| Tag Tier 2.json                   | Tag: Tier 2 with `tier2`                                                   |
| Tag Tier 3.json                   | Tag: Tier 3 with `tier3`                                                   |
| Tag Upload Limit Tier 2.json      | Tag: Tier 2 with `~2MB/s` and set upload speed to 2 MB/s if Ratio is > 2.0 |
| Tag Upload Limit Tier 3.json      | Tag: Tier 3 with `~1MB/s` and set upload speed to 1 MB/s if Ratio is > 2.0 |

## Movies

| Workflows                         | Description                                                                |
| --------------------------------- | -------------------------------------------------------------------------- |
| Delete noHL Tier 1.json           | Delete: noHL Tier 1 - after 21 days, If minimum seeders is 3, keep seeding |
| Delete noHL Tier 2.json           | Delete: noHL Tier 2 - after 21 days                                        |
| Delete noHL Tier 3.json           | Delete: noHL Tier 3 - after 21 days                                        |
| Delete problem cross-seeds.json   | Delete: cross-seed that have issues                                        |
| Delete unregistered torrents.json | Delete: unregistered torrents                                              |
| Tag noHL Tier 1.json              | Tag: noHL Tier 1 with `~Tier1-noHL-21`                                     |
| Tag noHL Tier 2.json              | Tag: noHL Tier 2 with `~Tier2-noHL-21`                                     |
| Tag noHL Tier 3.json              | Tag: noHL Tier 3 with `~Tier3-noHL-21`                                     |
| Tag noHL.json                     | Tag: torrents that are not hardlinked with `noHL`                          |
| Tag Tier 1.json                   | Tag: Tier 1 with `tier1`                                                   |
| Tag Tier 2.json                   | Tag: Tier 2 with `tier2`                                                   |
| Tag Tier 3.json                   | Tag: Tier 3 with `tier3`                                                   |
| Tag Upload Limit Tier 2.json      | Tag: Tier 2 with `~2MB/s` and set upload speed to 2 MB/s if Ratio is > 2.0 |
| Tag Upload Limit Tier 3.json      | Tag: Tier 3 with `~1MB/s` and set upload speed to 1 MB/s if Ratio is > 2.0 |

> [!NOTE]
> Tiers 1-3 are personal preferences. Put the trackers you prefer most or want to build a ratio for in Tier 1. You can always move them later to another Tier.

### Scripts

| Scripts                    | Description                                                                                       |
| -------------------------- | ------------------------------------------------------------------------------------------------- |
| qbittorrent_auto_tagger.py | Tags episodes when added to qBittorrent with `Episodes` so you can exempt them from cross-seeding |
