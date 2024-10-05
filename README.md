# mbgenre (Beets plugin)

The `mbgenre` plugin enhances your Beets library with genre data retrieved from Musicbrainz. Genres can be retrieved from the release, release group, or artist(s) associated with the release; or a combination of any three if you so desire.

Genre tags are applied to the album as well as each item in the album.

This functionality is unable to be natively supported by Beets, as the `python-musicbrainzngs` library does not retrieve this data (see [#266](https://github.com/alastair/python-musicbrainzngs/pull/266)). As such, this plugin implements support for this until a time where the Beets tagger can perform the same job.

## Installation

Install with pip:

```bash
    pip install beets-mbgenre
```

and then activate by adding to the list of plugins in your Beets config:

```yml
plugins:
    - mbgenre
```

## Configuration

The plugin supports several configuration options. These should be specified in your Beets config under the `mbgenre` key.

```yaml
mbgenre:
    # The maximum number of genre tags to be set on the album and its tracks. If not set, defaults to 1.
    max_genres: 1
    # If an album has genre tags set already, skip them.
    unset_only: yes
    # If more than one genre is retrieved, the separator between each genre. Defaults to ', ' if not set.
    separator: ", "
    # The order by which genres will be retrieved and added to the list. See "Source Order" below for a more detailed explanation.
    source_order:
        - release
        - release_group
        - artists
    # Convert each genre to title case. Defaults to False.
    title_case: no
```

### Source Order

The `source_order` configuration option provides two levels of configuration. If not set it defaults to `release`, then `release_group`, then `artists`.

Firstly, it gives the option of which sources to use for pulling tags. If an option is omitted then genre data is not retrieved from that source; for example if it was set to `artists` then only the artists' genres would be retrieved, and not those of the release or release group.

Secondly, it gives the option to prioritise where genre tags come from. For example if the option was set to `['artists', 'release']`, then the plugin would prioritise any genres associated with the Musicbrainz artist. Then, if there are still genre slots available (based on the `max_genres` config), then the remaining genres are populated with those of the release.
