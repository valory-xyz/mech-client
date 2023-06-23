.PHONY: eject-packages
eject-packages:
	rm -rf mech_client/helpers/p2p_libp2p_client
	cp -r packages/valory/connections/p2p_libp2p_client mech_client/helpers/p2p_libp2p_client

	rm -rf mech_client/helpers/acn
	cp -r packages/valory/protocols/acn mech_client/helpers/acn

	rm -rf mech_client/helpers/acn_data_share
	cp -r packages/valory/protocols/acn_data_share mech_client/helpers/acn_data_share

.PHONY: copy-packages-local
copy-packages-local:
	rm -rf packages/valory/connections/p2p_libp2p_client
	cp -r ~/mech/packages/valory/connections/p2p_libp2p_client packages/valory/connections/p2p_libp2p_client

	rm -rf packages/valory/protocols/acn
	cp -r ~/mech/packages/valory/protocols/acn packages/valory/protocols/acn

	rm -rf packages/valory/protocols/acn_data_share
	cp -r ~/mech/packages/valory/protocols/acn_data_share packages/valory/protocols/acn_data_share
