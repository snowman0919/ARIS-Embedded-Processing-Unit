from glob import glob
from os.path import join

from setuptools import setup

package_name = "aris_localization"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (join("share", package_name, "maps"), glob("maps/*.yaml")),
        (join("share", package_name, "worlds"), glob("worlds/*.sdf")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ARIS",
    maintainer_email="aris@example.invalid",
    description="V2 localization scaffolding for ARIS.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "lidar_localization_node = aris_localization.lidar_localization_node:main",
        ],
    },
)
