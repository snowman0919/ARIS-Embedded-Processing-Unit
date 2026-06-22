from setuptools import setup

package_name = "aris_mcu_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/mcu_bridge_sim.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ARIS",
    maintainer_email="aris@example.invalid",
    description="Simulation-safe ARIS MCU bridge and binary protocol reference.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "mcu_bridge_node = aris_mcu_bridge.bridge_node:main",
            "mcu_bridge_sim = aris_mcu_bridge.bridge_sim:main",
        ],
    },
)
