from __future__ import absolute_import, print_function
import atexit
import os
import os.path
import signal
from socket import socket
from subprocess import Popen, PIPE
from tempfile import NamedTemporaryFile
from time import sleep
from urllib import urlretrieve
from zipfile import ZipFile

import nltk

from .._downloader import _make_data_home, _progress


STANFORD_NER = (
    '''http://nlp.stanford.edu/software/stanford-ner-2014-01-04.zip'''
)


def download():
    home = _make_data_home()
    ner_dir = os.path.join(home, 'stanford-ner-2014-01-04')

    if not os.path.exists(ner_dir):
        with NamedTemporaryFile() as temp:
            urlretrieve(STANFORD_NER, temp.name, reporthook=_progress)
            with ZipFile(temp.name) as z:
                z.extractall(path=home)

    return ner_dir


# XXX the port number is completely arbitrary.
# Also, let's hope it's not available to the outside. Stanford doesn't seem to
# document this.
def start_server(port=9155):
    global ner_dir
    jar = os.path.join(ner_dir, 'stanford-ner.jar')
    model = os.path.join(ner_dir,
                         'classifiers/english.all.3class.distsim.crf.ser.gz')

    print("Starting Stanford NER on port %d" % port)
    server = Popen(['java', '-mx1000m', '-cp', jar,
                    'edu.stanford.nlp.ie.NERServer',
                    '-outputFormat', 'slashTags',
                    '-loadClassifier', model,
                    '-port', str(port)],
                   stderr=PIPE)

    def kill(p):
        p.send_signal(signal.SIGHUP)
        sleep(2)
        p.kill()
        p.wait()

    atexit.register(kill, server)

    stderr = server.stderr.readline()
    print(stderr, end='')
    if not 'done' in stderr:
        raise ValueError('cannot start Stanford NER')

    return server, port


# Download and start server at import, not call time. Import is done lazily.
ner_dir = download()
server, port = start_server()


def tag(doc):
    text = ' '.join(nltk.word_tokenize(doc))

    s = socket()
    s.connect(('localhost', port))
    s.sendall(text)
    s.send('\n')
    return [token.rsplit('/', 1) for token in s.recv(10 * len(text)).split()]
