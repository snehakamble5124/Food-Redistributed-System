from distributed_algorithms import MutualExclusion

donation_mutex = MutualExclusion(node_id="inventory-node-1")


def enter_donation_critical_section(donation_id: str, timeout: float = 10.0) -> bool:
    return donation_mutex.request_critical_section(donation_id, timeout=timeout)


def exit_donation_critical_section(donation_id: str):
    donation_mutex.release_critical_section(donation_id)
