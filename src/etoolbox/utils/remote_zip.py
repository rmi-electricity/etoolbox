"""Access files within a zip archive without downloading the full archive.

This remote_zip module and accompanying tests are lightly adapted from
the `python-remotezip <https://github.com/gtsystem/python-remotezip>`_ package written
by Giuseppe Tribulato (gtsystem) with contributions from Kim (SpicyGarlicAlbacoreRoll),
and M. Furkan (muhammedfurkan). From the original:

MIT License

Copyright (c) 2018 Giuseppe Tribulato

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including withlout limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import io
from itertools import tee
from zipfile import ZipFile

import requests

__all__ = ["RemoteIOError", "RemoteZip"]


class RemoteZipError(Exception):
    """Generic RemoteZip error."""

    pass


class OutOfBoundError(RemoteZipError):
    """Another error."""

    pass


class RemoteIOError(RemoteZipError):
    """IO error for RemoteZip."""

    pass


class RangeNotSupportedError(RemoteZipError):
    """Another range error."""

    pass


class _PartialBuffer:
    """An object with buffer-like interface but containing just a part of the data.

    The object allows to seek and read like this buffer contains the full data
    however, any attempt to read data outside the partial data is going to fail
    with OutOfBoundError error.
    """

    def __init__(self, buffer, offset, size, stream):
        self.buffer = buffer if stream else io.BytesIO(buffer.read())
        self._offset = offset
        self._size = size
        self._position = offset
        self._stream = stream

    def __len__(self):
        """Returns the data size contained in the buffer."""
        return self._size

    def __repr__(self):
        return f"<_PartialBuffer off={self._offset} size={self._size} stream={self._stream}>"

    def read(self, size=0):
        """Read data from the buffer from the current position."""
        if size == 0:
            size = self._offset + self._size - self._position

        content = self.buffer.read(size)
        self._position = self._offset + self.buffer.tell()
        return content

    def close(self):
        """Ensure memory and connections are closed."""
        if not self.buffer.closed:
            self.buffer.close()
            if hasattr(self.buffer, "release_conn"):
                self.buffer.release_conn()

    def tell(self):
        """Returns the current position on the virtual buffer."""
        return self._position

    def seek(self, offset, whence):
        """Change the position on the virtual buffer."""
        if whence == 2:
            self._position = self._size + self._offset + offset
        elif whence == 0:
            self._position = offset
        else:
            self._position += offset

        relative_position = self._position - self._offset

        if relative_position < 0 or relative_position >= self._size:
            raise OutOfBoundError("Position out of buffer bound")

        if self._stream:
            buff_pos = self.buffer.tell()
            if relative_position < buff_pos:
                raise OutOfBoundError("Negative seek not supported")

            skip_bytes = relative_position - buff_pos
            if skip_bytes == 0:
                return self._position
            self.buffer.read(skip_bytes)
        else:
            self.buffer.seek(relative_position)

        return self._position


class _RemoteIO(io.IOBase):
    """Exposes a file-like interface for zip files hosted remotely.

    It requires the remote server to support the Range header.
    """

    def __init__(self, fetch_fun, initial_buffer_size=64 * 1024):
        self._fetch_fun = fetch_fun
        self._initial_buffer_size = initial_buffer_size
        self.buffer = None
        self._file_size = None
        self._seek_succeeded = False
        self._member_position_to_size = None
        self._last_member_pos = None

    def set_position_to_size(self, position_to_size):
        self._member_position_to_size = position_to_size

    def read(self, size=0):
        position = self.tell()
        if size == 0:
            size = self._file_size - position

        if not self._seek_succeeded:
            if self._member_position_to_size is None:
                fetch_size = size
                stream = False
            else:
                try:
                    fetch_size = self._member_position_to_size[position]
                    self._last_member_pos = position
                except KeyError:
                    if self._last_member_pos and self._last_member_pos < position:
                        fetch_size = self._member_position_to_size[
                            self._last_member_pos
                        ]
                        fetch_size -= position - self._last_member_pos
                    else:
                        raise OutOfBoundError(
                            "Attempt to seek outside boundary of current zip member"
                        ) from None
                stream = True

            self._seek_succeeded = True
            self.buffer.close()
            self.buffer = self._fetch_fun(
                (position, position + fetch_size - 1), stream=stream
            )

        return self.buffer.read(size)

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if whence == 2 and self._file_size is None:
            size = self._initial_buffer_size
            self.buffer = self._fetch_fun((-size, None), stream=False)
            self._file_size = len(self.buffer) + self.buffer.tell()

        try:
            pos = self.buffer.seek(offset, whence)
            self._seek_succeeded = True
            return pos
        except OutOfBoundError:
            self._seek_succeeded = False
            return (
                self.tell()
            )  # we ignore the issue here, we will check if buffer is fine during read

    def tell(self):
        return self.buffer.tell()

    def close(self):
        if self.buffer:
            self.buffer.close()
            self.buffer = None


class _RemoteFetcher:
    """Represent a remote file to be fetched in parts."""

    def __init__(self, url, session=None, *, support_suffix_range=True, **kwargs):
        self._kwargs = kwargs
        self._url = url
        self._session = session
        self._support_suffix_range = support_suffix_range

    @staticmethod
    def parse_range_header(content_range_header):
        range_to_parse = content_range_header[6:].split("/")[0]
        if range_to_parse.startswith("-"):
            return int(range_to_parse), None
        range_min, range_max = range_to_parse.split("-")
        return int(range_min), int(range_max) if range_max else None

    @staticmethod
    def build_range_header(range_min, range_max):
        if range_max is None:
            return f"bytes={range_min}{'' if range_min < 0 else '-'}"
        return f"bytes={range_min}-{range_max}"

    def _request(self, kwargs):
        if self._session:
            res = self._session.get(self._url, stream=True, **kwargs)
        else:
            res = requests.get(self._url, stream=True, **kwargs)  # noqa: S113
        res.raise_for_status()
        if "Content-Range" not in res.headers:
            raise RangeNotSupportedError("The server doesn't support range requests")
        return res.raw, res.headers["Content-Range"]

    def prepare_request(self, data_range=None):
        kwargs = dict(self._kwargs)
        kwargs["headers"] = headers = dict(kwargs.get("headers", {}))
        if data_range is not None:
            headers["Range"] = self.build_range_header(*data_range)
        return kwargs

    def get_file_size(self):
        if self._session:
            res = self._session.head(self._url, **self.prepare_request())
        else:
            res = requests.head(self._url, **self.prepare_request())  # noqa: S113
        try:
            res.raise_for_status()
            return int(res.headers["Content-Length"])
        except OSError as exc:
            raise RemoteIOError(str(exc)) from exc
        except KeyError as exc:
            raise RemoteZipError(
                "Cannot get file size: Content-Length header missing"
            ) from exc

    def fetch(self, data_range, *, stream=False):
        """Fetch a part of a remote file."""
        # Handle the case suffix range request is not supported. Fixes #15
        if (
            data_range[0] < 0
            and data_range[1] is None
            and not self._support_suffix_range
        ):
            size = self.get_file_size()
            data_range = (max(0, size + data_range[0]), size - 1)

        kwargs = self.prepare_request(data_range)
        try:
            res, range_header = self._request(kwargs)
            range_min, range_max = self.parse_range_header(range_header)
            return _PartialBuffer(res, range_min, range_max - range_min + 1, stream)
        except OSError as exc:
            raise RemoteIOError(str(exc)) from exc


def _pairwise(iterable):
    """pairwise('ABCDEFG') --> AB BC CD DE EF FG."""
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b, strict=False)


class RemoteZip(ZipFile):
    """ZipFile that only downloads files when you ask for them."""

    def __init__(  # noqa: D417
        self,
        url: str,
        initial_buffer_size: int = 64 * 1024,
        session=None,
        fetcher=_RemoteFetcher,
        *,
        support_suffix_range: bool = True,
        **kwargs,
    ):
        """Create a object that represents a remote zip file.

        Args:
            url: URL to the remote zip file.
            initial_buffer_size:
            session:
            fetcher:
            support_suffix_range:
            **kwargs:
        """
        fetcher = fetcher(
            url, session, support_suffix_range=support_suffix_range, **kwargs
        )
        rio = _RemoteIO(fetcher.fetch, initial_buffer_size)
        super().__init__(rio)
        rio.set_position_to_size(self._get_position_to_size())

    def _get_position_to_size(self):
        ilist = [info.header_offset for info in self.infolist()]
        if len(ilist) == 0:
            return {}
        ilist.sort()
        ilist.append(self.start_dir)
        return {a: b - a for a, b in _pairwise(ilist)}
