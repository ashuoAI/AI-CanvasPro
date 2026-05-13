(function() {
  var _originalLocalStorage = window.localStorage;

  var GLOBAL_KEY_PREFIXES = [
    'aic-',
    '__aic',
    'v2-canvas',
    'v2-workspace',
    'v2-project',
    'dreamina-resume-'
  ];

  var GLOBAL_EXACT_KEYS = {
    'aic-install-id': true,
    'aic-v54-vip-unlocked': true,
    '__aicInstallId': true
  };

  function _isGlobalKey(key) {
    if (GLOBAL_EXACT_KEYS[key]) return true;
    for (var i = 0; i < GLOBAL_KEY_PREFIXES.length; i++) {
      if (key.indexOf(GLOBAL_KEY_PREFIXES[i]) === 0) return true;
    }
    return false;
  }

  function _isAlreadyScoped(key) {
    return /^user_\d+_/.test(key);
  }

  function _getCurrentUserId() {
    try {
      var raw = sessionStorage.getItem('aic_session');
      if (!raw) return null;
      var session = JSON.parse(raw);
      var user = session.user || null;
      if (!user) return null;
      return user.id || user.user_id || user.ID || null;
    } catch(e) {
      return null;
    }
  }

  function _scopeKey(key) {
    if (_isGlobalKey(key) || _isAlreadyScoped(key)) return key;
    var uid = _getCurrentUserId();
    if (!uid) return key;
    return 'user_' + uid + '_' + key;
  }

  var _userScopedStorage = {
    getItem: function(key) {
      return _originalLocalStorage.getItem(_scopeKey(String(key)));
    },
    setItem: function(key, value) {
      return _originalLocalStorage.setItem(_scopeKey(String(key)), String(value));
    },
    removeItem: function(key) {
      return _originalLocalStorage.removeItem(_scopeKey(String(key)));
    },
    clear: function() {
      var uid = _getCurrentUserId();
      if (!uid) {
        _originalLocalStorage.clear();
        return;
      }
      var prefix = 'user_' + uid + '_';
      var keysToRemove = [];
      for (var i = 0; i < _originalLocalStorage.length; i++) {
        var k = _originalLocalStorage.key(i);
        if (k && k.indexOf(prefix) === 0) {
          keysToRemove.push(k);
        }
      }
      for (var j = 0; j < keysToRemove.length; j++) {
        _originalLocalStorage.removeItem(keysToRemove[j]);
      }
    },
    key: function(index) {
      return _originalLocalStorage.key(index);
    },
    get length() {
      return _originalLocalStorage.length;
    }
  };

  try {
    Object.defineProperty(window, 'localStorage', {
      value: _userScopedStorage,
      writable: true,
      configurable: true
    });
  } catch(e) {
    window.__userScopedStorage = _userScopedStorage;
  }
})();