import pickle
import re
import hashlib
import threading

from .logger.log import debug, error, warn
from .banco import Banco
import os

def _save(file_name):
    CONEXAO_BANCO.executarComandoSQLSemRetorno("INSERT OR IGNORE INTO CACHE(cache_file) VALUES ('{0}')".format(file_name))


def _get(id):
    return CONEXAO_BANCO.executarComandoSQLSelect("SELECT cache_file FROM CACHE WHERE cache_file = '{0}'".format(id))


def _remove(id):
    CONEXAO_BANCO.executarComandoSQLSemRetorno("DELETE FROM CACHE WHERE cache_file = '{0}';".format(id))


def _get_file_name(id):
    return "{0}.{1}".format(id, "ipcache")


def _get_id(fun_name, fun_args, fun_source):
    return hashlib.md5((fun_name + str(fun_args) + fun_source).encode('utf')).hexdigest()


def get_cache_data(fun_name, fun_args, fun_source):
    id = _get_id(fun_name, fun_args, fun_source)
    
    #Checking if the result is saved in the cache
    with CACHED_DATA_DICTIONARY_SEMAPHORE:
        if(id in CACHED_DATA_DICTIONARY):
            return CACHED_DATA_DICTIONARY[id]

    #Checking if the result was already processed at this execution
    if(id in NEW_DATA_DICTIONARY):
        return NEW_DATA_DICTIONARY[id]

    return None


def autofix(id):
    debug("starting autofix")
    debug("removing {0} from database".format(id))
    _remove(_get_file_name(id))
    debug("environment fixed")


def create_entry(fun_name, fun_args, fun_return, fun_source):
    id = _get_id(fun_name, fun_args, fun_source)
    NEW_DATA_DICTIONARY[id] = fun_return

def salvarNovosDadosBanco():
    def serialize(return_value, file_name):
        with open(".intpy/cache/{0}".format(_get_file_name(file_name)), 'wb') as file:
            return pickle.dump(return_value, file, protocol=pickle.HIGHEST_PROTOCOL)
    
    for id in NEW_DATA_DICTIONARY:
        debug("serializing return value from {0}".format(id))
        serialize(NEW_DATA_DICTIONARY[id], id)

        debug("inserting reference in database")
        _save(_get_file_name(id))

    CONEXAO_BANCO.salvarAlteracoes()
    CONEXAO_BANCO.fecharConexao()

def deserialize(id):
    try:
        with open(".intpy/cache/{0}".format(_get_file_name(id)), 'rb') as file:
            return pickle.load(file)
    except FileNotFoundError as e:
        warn("corrupt environment. Cache reference exists for a function in database but there is no file for it in cache folder.\
Have you deleted cache folder?")
        autofix(id)
        return None

def populate_cached_data_dictionary():
    db_connection = Banco(os.path.join(".intpy", "intpy.db"))
    list_of_ipcache_files = db_connection.executarComandoSQLSelect("SELECT cache_file FROM CACHE")
    for ipcache_file in list_of_ipcache_files:
        ipcache_file = ipcache_file[0].replace(".ipcache", "")
        
        result = deserialize(ipcache_file)
        if(result is None):
            continue
        else:
            with CACHED_DATA_DICTIONARY_SEMAPHORE:
                CACHED_DATA_DICTIONARY[ipcache_file] = result
    db_connection.fecharConexao()

CACHED_DATA_DICTIONARY = {}

CACHED_DATA_DICTIONARY_SEMAPHORE = threading.Semaphore()
load_cached_data_dictionary_thread = threading.Thread(target=populate_cached_data_dictionary)
load_cached_data_dictionary_thread.start()

#Opening database connection and creating select query to the database
#to populate CACHED_DATA_DICTIONARY
CONEXAO_BANCO = Banco(os.path.join(".intpy", "intpy.db"))

NEW_DATA_DICTIONARY = {}
