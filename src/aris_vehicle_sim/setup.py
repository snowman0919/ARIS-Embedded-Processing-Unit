from glob import glob
from os.path import join

from setuptools import setup

package_name = "aris_vehicle_sim"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (
            f"share/{package_name}/launch",
            [
                "launch/pure_sim.launch.py",
                "launch/autonomous_sim.launch.py",
                "launch/autonomous_rviz.launch.py",
                "launch/rviz.launch.py",
                "launch/gazebo.launch.py",
                "launch/lidar_sim.launch.py",
            ],
        ),
        (f"share/{package_name}/rviz", ["rviz/autonomous_sim.rviz"]),
        (join("share", package_name, "config"), glob("config/*.yaml")),
        (join("share", package_name, "maps"), glob("maps/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ARIS",
    maintainer_email="aris@example.invalid",
    description="Minimal ARIS vehicle simulation package.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "vehicle_sim_node = aris_vehicle_sim.vehicle_sim_node:main",
            "lidar_sim_node = aris_vehicle_sim.lidar_sim_node:main",
        ],
    },
)
