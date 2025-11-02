from unittest import mock

from nix_heuristic_gc import libnixstore_wrapper as libstore
from nix_heuristic_gc.graph import GarbageGraph
from nix_heuristic_gc.quantity import QuantityUnit


def _raise_if_exc(val):
    if isinstance(val, Exception):
        raise val
    return val


@mock.patch("nix_heuristic_gc.graph._nix_store_path", new="/nix/store")
@mock.patch("nix_heuristic_gc.graph._gc_keep_derivations", new=False)
@mock.patch("nix_heuristic_gc.graph._gc_keep_outputs", new=False)
@mock.patch("nix_heuristic_gc.graph.path_stat_agg", autospec=True)
def test_basic_init(
    mock_path_stat_agg,
):
        mock_path_stat_agg.return_value = 123, 123, 123

        mock_store = mock.create_autospec(
            libstore.Store,
            spec_set=True,
            instance=True,
        )
        mock_store.collect_garbage.return_value = {
            "/nix/store/11111111111111111111111111111111-111-1.1.1",
            "/nix/store/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2",
            "/nix/store/cccccccccccccccccccccccccccccccc-ccc-3.3.3",
            "/nix/store/dddddddddddddddddddddddddddddddd-ddd-4.4.4",
            "/nix/store/55555555555555555555555555555555-555-5.5.5",
            "/nix/store/666-6.6.6",
            "/nix/store/77777777777777777777777777777777-777-7.7.7",
        }, 0
        mock_store.topo_sort_paths.return_value = [
            libstore.StorePath("77777777777777777777777777777777-777-7.7.7"),
            libstore.StorePath("55555555555555555555555555555555-555-5.5.5"),
            libstore.StorePath("dddddddddddddddddddddddddddddddd-ddd-4.4.4"),
            libstore.StorePath("cccccccccccccccccccccccccccccccc-ccc-3.3.3"),
            libstore.StorePath("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2"),
            libstore.StorePath("11111111111111111111111111111111-111-1.1.1"),
        ]
        mock_store.query_path_info.side_effect = lambda store_path: _raise_if_exc({
            "11111111111111111111111111111111-111-1.1.1": mock.Mock(
                autospec = libstore.ValidPathInfo,
                references = set(),
                nar_size = 123,
                path = libstore.StorePath("11111111111111111111111111111111-111-1.1.1"),
            ),
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2": mock.Mock(
                autospec = libstore.ValidPathInfo,
                references = {libstore.StorePath("11111111111111111111111111111111-111-1.1.1")},
                nar_size = 123,
                path = libstore.StorePath("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2"),
            ),
            "cccccccccccccccccccccccccccccccc-ccc-3.3.3": mock.Mock(
                autospec = libstore.ValidPathInfo,
                references = {libstore.StorePath("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2")},
                nar_size = 123,
                path = libstore.StorePath("cccccccccccccccccccccccccccccccc-ccc-3.3.3"),
            ),
            "dddddddddddddddddddddddddddddddd-ddd-4.4.4": mock.Mock(
                autospec = libstore.ValidPathInfo,
                references = {libstore.StorePath("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2")},
                nar_size = 123,
                path = libstore.StorePath("dddddddddddddddddddddddddddddddd-ddd-4.4.4"),
            ),
            "55555555555555555555555555555555-555-5.5.5": mock.Mock(
                autospec = libstore.ValidPathInfo,
                references = set(),
                nar_size = 123,
                path = libstore.StorePath("55555555555555555555555555555555-555-5.5.5"),
            ),
            "77777777777777777777777777777777-777-7.7.7": RuntimeError("nope"),
        }[str(store_path)])

        garbage_graph = GarbageGraph(mock_store, QuantityUnit.BYTES)

        assert mock_store.mock_calls[:2] == [
            mock.call.collect_garbage(action=libstore.GCAction.GCReturnDead),
            mock.call.topo_sort_paths({
                libstore.StorePath("11111111111111111111111111111111-111-1.1.1"),
                libstore.StorePath("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2"),
                libstore.StorePath("cccccccccccccccccccccccccccccccc-ccc-3.3.3"),
                libstore.StorePath("dddddddddddddddddddddddddddddddd-ddd-4.4.4"),
                libstore.StorePath("55555555555555555555555555555555-555-5.5.5"),
                libstore.StorePath("77777777777777777777777777777777-777-7.7.7"),
            }),
        ]
        assert sorted(mock_store.mock_calls[2:]) == sorted((
            mock.call.query_path_info(libstore.StorePath("77777777777777777777777777777777-777-7.7.7")),
            mock.call.query_path_info(libstore.StorePath("55555555555555555555555555555555-555-5.5.5")),
            mock.call.query_path_info(libstore.StorePath("dddddddddddddddddddddddddddddddd-ddd-4.4.4")),
            mock.call.query_path_info(libstore.StorePath("cccccccccccccccccccccccccccccccc-ccc-3.3.3")),
            mock.call.query_path_info(libstore.StorePath("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbb-2.2.2")),
            mock.call.query_path_info(libstore.StorePath("11111111111111111111111111111111-111-1.1.1")),
        ))

        assert mock_path_stat_agg.mock_calls == [
            mock.call("/nix/store/cccccccccccccccccccccccccccccccc-ccc-3.3.3"),
            mock.call("/nix/store/dddddddddddddddddddddddddddddddd-ddd-4.4.4"),
            mock.call("/nix/store/55555555555555555555555555555555-555-5.5.5"),
            mock.call("/nix/store/77777777777777777777777777777777-777-7.7.7"),
        ]

        assert garbage_graph.very_invalid_paths == {
            "/nix/store/666-6.6.6",
        }
