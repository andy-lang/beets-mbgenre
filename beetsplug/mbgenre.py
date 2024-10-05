import dataclasses
import enum

from beets import plugins, ui, library
import httpx


@dataclasses.dataclass
class MusicbrainzGenre:
    name: str
    count: int = 0


@dataclasses.dataclass
class GenreCollection:
    artists: list[MusicbrainzGenre] = dataclasses.field(default_factory=list)
    release_group: list[MusicbrainzGenre] = dataclasses.field(default_factory=list)
    release: list[MusicbrainzGenre] = dataclasses.field(default_factory=list)

    def sort(self):
        for key in self.__annotations__.keys():
            data = getattr(self, key, None)
            if data:
                sorted_data = sorted(data, key=lambda d: d.count, reverse=True)
                setattr(self, key, sorted_data)


class GenreSource(str, enum.Enum):
    release = "release"
    release_group = "release_group"
    artists = "artists"


class MbGenre(plugins.BeetsPlugin):
    def __init__(self):
        super().__init__()

        self.config.add(
            {
                "max_genres": 5,
                "unset_only": True,
                "separator": ", ",
                "source_order": [
                    GenreSource.release,
                    GenreSource.release_group,
                    GenreSource.artists,
                ],
                "title_case": False,
            }
        )
        self.import_stages = [self.genre_tag_stage]

    def _get_mb_release(self, album: library.Album) -> dict:
        # Work out which sections of the release to include, based on source_order queries.
        include_params = ["genres"]
        if GenreSource.release_group in self.config["source_order"].get():
            include_params.append("release-groups")

        if GenreSource.artists in self.config["source_order"].get():
            include_params.append("artists")

        # Grab the release from Musicbrainz.
        with httpx.Client(base_url="https://musicbrainz.org/ws/2") as client:
            response = client.request(
                "GET",
                f"release/{album.mb_albumid}",
                # Genres aren't included in query responses by default, so make sure we include these.
                # We are requesting 'genres' here but this will also return artist & release group genres.
                params={"inc": " ".join(include_params)},
                # Make sure we grab results
                headers={"accept": "application/json"},
            )

        js = response.json()
        if "error" in js:
            raise ValueError(js["error"])
        return js

    def _parse_genre_list(self, l) -> list[MusicbrainzGenre]:
        genres = list()
        for genre_dict in l:
            genre = MusicbrainzGenre(
                name=genre_dict["name"].strip(), count=genre_dict.get("count", 0)
            )
            genres.append(genre)
        return genres

    def _get_genres_for_source(
        self, mb_response: dict, source: GenreSource
    ) -> list[MusicbrainzGenre]:
        genres = list()

        if source == GenreSource.artists:
            for artist_dict in mb_response["artist-credit"]:
                genres += self._parse_genre_list(artist_dict["artist"]["genres"])

        elif source == GenreSource.release_group:
            genres = self._parse_genre_list(mb_response["release-group"]["genres"])

        elif source == GenreSource.release:
            genres = self._parse_genre_list(mb_response["genres"])

        return genres

    def _get_genres(self, album: library.Album) -> str:
        if not album.mb_albumid:
            raise ValueError("No Musicbrainz album ID is set in Beets library metadata")

        mb_response = self._get_mb_release(album)

        collection = GenreCollection()

        for source in self.config["source_order"].get():
            genres = self._get_genres_for_source(mb_response, source)
            setattr(collection, source, genres)

        collection.sort()

        genres = list()
        for source in self.config["source_order"].get():
            genres += getattr(collection, source)

        genre_strs = list()
        for genre in genres:
            if genre.name not in genre_strs:
                genre_strs.append(genre.name)

        max_genres = self.config["max_genres"].get()
        if max_genres:
            genre_strs = genre_strs[:max_genres]

        if self.config["title_case"].get():
            genre_strs = [genre.title() for genre in genre_strs]

        separator = self.config["separator"].get()
        return separator.join(genre_strs)

    def _save_album_genre_data(self, album: library.Album, genres: str, write: bool):
        if not genres:
            self._log.warning("{0}: No genres found - no changes will be made", album)
            return

        self._log.info("{0}: {1}", album, genres)
        album.genre = genres
        album.store()

        for item in album.items():
            item.genre = genres
            item.store()
            if write:
                item.try_write()

    def commands(self):
        command = ui.Subcommand(
            "mbgenre", help="Add genres to tracks from Musicbrainz tags"
        )

        def func(lib, opts, args):
            write = ui.should_write()
            self.config.set_args(opts)

            # TODO there's gotta be a better way of doing this that doesn't require so many API calls.
            # Is there a way we can make multiple queries at once to avoid the network latency of a one-by-one query?
            for album in lib.albums(ui.decargs(args)):
                if self.config["unset_only"].get() and album.genre:
                    self._log.debug(f"{0}: Skipping - genre data already set", album)
                    continue
                self._log.debug("Getting genres for {0}", album)
                try:
                    genres = self._get_genres(album)
                    self._save_album_genre_data(album, genres, write)
                except ValueError as e:
                    self._log.warning("{0}: skipping - {1}", album, str(e))
                    continue

        command.func = func
        return [command]

    def genre_tag_stage(self, session, task):
        if task.is_album:
            self._log.debug("Getting genres for {0}", task.album)
            try:
                if self.config["unset_only"].get() and task.album.genre:
                    self._log.debug(
                        f"{0}: Skipping - genre data already set", task.album
                    )
                    return

                genres = self._get_genres(task.album)
                self._save_album_genre_data(task.album, genres, False)
            except ValueError as e:
                self._log.warning(str(e))
                return

        else:
            self._log.warning(
                "Not an album, cannot get release genre data from Musicbrainz"
            )
