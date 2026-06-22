from setuptools import setup

package_name = "aris_perception"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ARIS",
    maintainer_email="aris@example.invalid",
    description="Simulation-only perception scaffolds for ARIS V3.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "gazebo_cloud_adapter_node = aris_perception.gazebo_cloud_adapter_node:main",
            "simulated_segmentation_node = aris_perception.simulated_segmentation_node:main",
        ],
    },
)
