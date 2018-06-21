# -*- encoding: utf-8
#
# Copyright (c) 2017 Alex Chan
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# https://github.com/alexwlchan/lazyreader

def lazyread(f, delimiter):
    """
    Generator which continually reads ``f`` to the next instance
    of ``delimiter``.
    This allows you to do batch processing on the contents of ``f`` without
    loading the entire file into memory.
    :param f: Any file-like object which has a ``.read()`` method.
    :param delimiter: Delimiter on which to split up the file.
    """
    # Get an empty string to start with.  We need to make sure that if the
    # file is opened in binary mode, we're using byte strings, and similar
    # for Unicode.  Otherwise trying to update the running string will
    # hit a TypeError.
    try:
        running = f.read(0)
    except Exception as e:

        # The boto3 APIs don't let you read zero bytes from an S3 object, but
        # they always return bytestrings, so in this case we know what to
        # start with.
        if e.__class__.__name__ == 'IncompleteReadError':
            running = b''
        else:
            raise

    while True:
		# Empirically increased the buffer chunk size from the original 1024.
		# This way the reading seems to be faster
        new_data = f.read(102400)

        # When a call to read() returns nothing, we're at the end of the file.
        if not new_data:
            yield running
            return

        # Otherwise, update the running stream and look for instances of
        # the delimiter.  Remember we might have read more than one delimiter
        # since the last time we checked
        running += new_data
        while delimiter in running:
            curr, running = running.split(delimiter, 1)
            yield curr + delimiter
