ENV['VAGRANT_EXPERIMENTAL']='disks'

Vagrant.configure("2") do |config|
	config.vm.box = "ubuntu/jammy64"
	config.ssh.forward_agent = true

	config.vm.provider "virtualbox" do |vb|
		vb.cpus = 2
		vb.memory = "8192"
		vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
	end

	config.vm.define "build-lva" do |node|
		node.vm.hostname = "build-lva"
		node.vm.disk :disk, size: "100GB", primary: true
		node.vm.synced_folder ".provision/", "/tmp/.provision"
		node.vm.synced_folder "./", "/home/vagrant/build"

		node.vm.provision "shell", inline: <<-SCRIPT
			UBUNTU_CODENAME=$(lsb_release -cs)

			# Выбираем зеркало (можно изменить на предпочитаемое)
			MIRROR="mirror.yandex.ru/ubuntu"
			# Альтернатива: MIRROR="mirror.timeweb.ru/ubuntu"

			# Создаем резервную копию sources.list
			echo "Создаем резервную копию /etc/apt/sources.list -> /etc/apt/sources.list.bak"
			cp /etc/apt/sources.list /etc/apt/sources.list.bak

			# Заменяем репозитории на выбранное зеркало
			echo "Заменяем репозитории на $MIRROR..."
			sed -i "s|http://.*archive.ubuntu.com/ubuntu|http://${MIRROR}|g" /etc/apt/sources.list
			sed -i "s|http://.*security.ubuntu.com/ubuntu|http://${MIRROR}|g" /etc/apt/sources.list
		SCRIPT

		node.vm.provision :salt do |salt|
			salt.masterless = true
			salt.colorize = true
			salt.verbose = true
			salt.log_level = "info"
			salt.install_type = "stable"
			salt.version = "3006.9"
			salt.run_highstate = true
			salt.salt_call_args = ["--file-root", "/tmp/.provision"]

			salt.pillar({})
		end

		# https://dh1tw.de/2019/12/cross-compiling-golang-cgo-projects/
		# https://askubuntu.com/questions/1255707/apt-cant-find-packages-on-ubuntu-20-04-arm64-raspberry-pi-4
		node.vm.provision "shell", inline: <<-SCRIPT
			apt-get install -y binfmt-support qemu-user-static
			dpkg --add-architecture arm64
			cat > /etc/apt/sources.list.d/arm64.list <<EOF
deb [arch=arm64] http://ports.ubuntu.com/ focal main multiverse universe
deb [arch=arm64] http://ports.ubuntu.com/ focal-security main multiverse universe
deb [arch=arm64] http://ports.ubuntu.com/ focal-backports main multiverse universe
deb [arch=arm64] http://ports.ubuntu.com/ focal-updates main multiverse universe
EOF

			apt-get update
			apt-get install -y gcc-aarch64-linux-gnu
		SCRIPT

		node.vm.provision "shell", inline: <<-SCRIPT
			if ! grep "cd /home/vagrant/build" /home/vagrant/.profile ; then
				echo 'cd /home/vagrant/build' >> /home/vagrant/.profile
			fi
		SCRIPT
	end
end
