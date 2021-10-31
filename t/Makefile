bats = ./bats-core

vm1.tests: $(bats) 
	export TEST=vm1 ; ./bats-core/bin/bats tests.bats
vm2.tests: $(bats)
	export TEST=vm2 ; ./bats-core/bin/bats tests.bats
vm3.tests: $(bats)
	export TEST=vm3 ; ./bats-core/bin/bats tests.bats
vm4.tests: $(bats)
	export TEST=vm4 ; ./bats-core/bin/bats tests.bats


all: | $(bats) vm1.tests vm2.tests vm3.tests vm4.tests

clean:
	@rm -rf $(bats)
	@rm -rf /tmp/testset*
	@rm -f /tmp/backup.zip
	@rm -f /tmp/*vm*.qcow2
	@rm -f *.cpt
	@rm -f *.log
	@rm -rf checkpoints
	@rm -f vmconfig*.xml
	for vm in vm1 vm2 vm3 vm4 vm5; do \
		virsh destroy $$vm ; \
		virsh undefine $$vm --checkpoints-metadata ; \
	done

$(bats):
	@git clone https://github.com/bats-core/bats-core

.PHONY: all
