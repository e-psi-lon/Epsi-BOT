import pkg_resources
import os


def check_version(package, version):
    try:
        if package.startswith("git+"):
            # On split les / et on prend le dernier element pour avoir le nom du package et l'avant dernier pour le nom de l'auteur 
            package = package.split("/")[-2] + "/" + package.split("/")[-1].split(".git")[0]
            latest_version = get_git_latest_version(package)
        else:
            latest_version = get_pip_latest_version(package)
    except:
        return version, version
    return latest_version, version


def get_pip_latest_version(package):
    import requests
    return requests.get(f"https://pypi.org/pypi/{package}/json").json()["info"]["version"]


def get_git_latest_version(package):
    import requests
    return requests.get(f"https://api.github.com/repos/{package}/releases/latest").json()["tag_name"]


def check_updates():
    with open("requirements.txt") as f:
        # Sachant que les requirements c'est des == mais aussi des ~=
        packages = [line.strip().split("==" if not line.startswith("git+") else "@") for line in f.readlines() if
                    line.strip() and not line.startswith("#")]
        packages = [[package[0], "latest"] if len(package) == 1 else package for package in packages]
    for package, version in packages:
        latest_version, version = check_version(package, version)
        if latest_version != version and version != "latest":
            yield package, version, latest_version


def update_requirements():
    with open("requirements.txt") as f:
        # On split les == pour les libs normales et les @ pour les libs git
        packages = [line.strip().split("==" if not line.startswith("git+") else "@") for line in f.readlines() if
                    line.strip() and not line.startswith("#")]
        packages = [[package[0], "latest"] if len(package) == 1 else package for package in packages]
    with open("requirements.txt", "w") as f:
        for package, version in packages:
            latest_version, version = check_version(package, version)
            f.write(f"{package}=={latest_version}\n")


def get_installed_packages():
    installed_packages = []
    for dist in pkg_resources.working_set:
        package_name = dist.project_name
        package_version = dist.version

        # Gérer les cas spéciaux
        extras = dist._dep_map.keys()
        if "async" in extras:
            package_name += "[async]"

        installed_packages.append([package_name, package_version])

    return installed_packages


def check_libs():
    installed_packages = [package for package in get_installed_packages()]
    with open("requirements.txt") as f:
        packages = [line.strip().split("==" if "==" in line else "~=") for line in f.readlines() if
                    line.strip() and not line.startswith("#") and not line.startswith("git+")]
    for package, version in packages:
        for installed_package, installed_version in installed_packages:
            if package == installed_package:
                if version != installed_version:
                    yield package, version, installed_version
                break
        else:
            yield package, version, None


def update_libs(libs):
    for lib in libs:
        os.popen(f"python -m pip install --upgrade {lib}")
