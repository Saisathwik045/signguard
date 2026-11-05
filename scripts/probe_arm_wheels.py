"""Metadata-only ARM64 wheel availability probe, not an ARM runtime qualification."""
import json
import urllib.request

PACKAGES={'pyHanko':'0.35.2','pymupdf':'1.28.2','opencv-python-headless':'4.14.0.94',
          'numpy':'2.5.4','pillow':'13.0.0','cryptography':'50.0.2','lxml':'6.1.3','cffi':'2.1.1'}


def probe():
    result={}
    for package,version in PACKAGES.items():
        try:
            with urllib.request.urlopen('https://pypi.org/pypi/'+package+'/'+version+'/json',timeout=20) as response:
                data=json.load(response)
            names=[item['filename'] for item in data['urls'] if item['packagetype']=='bdist_wheel'
                   and not item.get('yanked') and ('aarch64' in item['filename'] or 'none-any.whl' in item['filename'])]
            result[package]={'version':version,'arm64_or_pure_wheels':names,'metadata_available':True}
        except (OSError,ValueError) as error:
            result[package]={'version':version,'metadata_available':False,'error_type':type(error).__name__}
    return {'packages':result,'python_abi_compatibility_verified':False,'native_runtime_verified':False,
            'poppler_apt_install_verified':False,'oracle_capacity_verified':False}


if __name__=='__main__':print(json.dumps(probe(),indent=2))
