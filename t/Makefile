bats = ./bats-core

vm1.tests: $(bats)
	export TEST=vm1 ; ./bats-core/bin/bats tests.bats
vm2.tests: $(bats)
	export TEST=vm2 ; ./bats-core/bin/bats tests.bats
vm3.tests: $(bats)
	export TEST=vm3 ; ./bats-core/bin/bats tests.bats

all: | $(bats) vm1.tests vm2.tests vm3.tests

clean:
	@rm -rf $(bats)
	for vm in vm1 vm2 vm3; do \
		virsh destroy $$vm ; \
		virsh undefine $$vm --remove-all-storage --checkpoints-metadata ; \
	done

$(bats):
	@git clone https://github.com/bats-core/bats-core

.PHONY: all
