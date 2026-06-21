from glob import glob
from os.path import join

from setuptools import setup

package_name = "aris_planning"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "README.md"]),
        (join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ARIS",
    maintainer_email="aris@example.invalid",
    description="Starter global and local planners for ARIS simulation.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "local_planner_node = aris_planning.local_planner_node:main",
            "path_recorder_node = aris_planning.path_recorder_node:main",
            "global_planner_node = aris_planning.global_planner_node:main",
        ],
    },
)
