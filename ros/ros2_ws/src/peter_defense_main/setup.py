from setuptools import find_packages, setup

setup(
    name='peter_defense_main', version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/peter_defense_main']),
        ('share/peter_defense_main', ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Peter Defense', maintainer_email='maintainer@example.com',
    description='Main-side compressed image subscriber', license='Apache-2.0',
    entry_points={'console_scripts': [
        'image_subscriber = peter_defense_main.image_subscriber:main',
    ]},
)
