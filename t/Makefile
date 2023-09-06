bats = ./bats-core

vm1.tests: $(bats) 
	$(call clean)
	export TEST=vm1 ; ./bats-core/bin/bats tests.bats
vm2.tests: $(bats)
	$(call clean)
	export TEST=vm2 ; ./bats-core/bin/bats tests.bats
vm3.tests: $(bats)
	$(call clean)
	export TEST=vm3 ; ./bats-core/bin/bats tests.bats
vm4.tests: $(bats)
	$(call clean)
	export TEST=vm4 ; ./bats-core/bin/bats tests.bats
vm5.tests: $(bats)
	$(call clean)
	export TEST=vm5 ; ./bats-core/bin/bats tests.bats


all: | $(bats) vm1.tests vm2.tests vm3.tests vm4.tests

clean:
	$(call clean)

define clean
	@rm -rf /tmp/testset*
	@rm -f /tmp/backup.zip
	@rm -f /tmp/*vm*.qcow2
	@rm -f *.cpt
	@rm -f *.log
	@rm -rf checkpoints
	@rm -f vmconfig*.xml
	@umount -lf /empty || true
	for vm in vm1 restore_vm1 vm2 vm3 vm4 vm5; do \
		if virsh list --all | grep $$vm; then \
			virsh destroy $$vm; \
			virsh undefine $$vm --checkpoints-metadata --nvram --managed-save; \
		fi \
	done
endef

$(bats):
	@git clone https://github.com/bats-core/bats-core

.PHONY: all
