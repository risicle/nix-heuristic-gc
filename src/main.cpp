#include <pybind11/operators.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#define _STRINGIFY_MACRO(x) #x
#define SYSTEM _STRINGIFY_MACRO(NIX_SYSTEM)
#include <nix/callback.hh>
#include <nix/gc-store.hh>
#include <nix/shared.hh>
#include <nix/store-cast.hh>
#include <nix/store-api.hh>
#include <nix/remote-store.hh>
#include <nix/local-store.hh>
#include <nix/local-fs-store.hh>
#undef SYSTEM

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;


PYBIND11_MODULE(libnixstore_wrapper, m) {
    m.doc() = R"pbdoc(
        libnixstore wrapper
        -------------------
    )pbdoc";

    auto get_event_loop = py::module_::import("asyncio.events").attr("get_event_loop");
    auto RuntimeError = py::module_::import("builtins").attr("RuntimeError");

    nix::initNix();

    m.def("get_nix_store_path", [](){
        return nix::settings.nixStore;
    });
    m.def("get_gc_keep_derivations", []() -> bool {
        return nix::settings.gcKeepDerivations;
    });
    m.def("get_gc_keep_outputs", []() -> bool {
        return nix::settings.gcKeepOutputs;
    });

    py::class_<nix::StorePath>(m, "StorePath")
        .def(py::init<const std::string &>())
        .def("__str__", &nix::StorePath::to_string)
        .def("__repr__", [](const nix::StorePath& store_path){
            return "StorePath(\"" + std::string(store_path.to_string()) + "\")";
        })
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self < py::self)
        .def("__hash__", [](const nix::StorePath& store_path){
            return py::hash(py::str(store_path.to_string()));
        });

    py::class_<nix::ValidPathInfo, std::shared_ptr<nix::ValidPathInfo>>(m, "ValidPathInfo")
        .def("__repr__", [](const nix::ValidPathInfo& path_info){
            return "ValidPathInfo(\"" + std::string(path_info.path.to_string()) + "\")";
        })
        .def_readonly("path", &nix::ValidPathInfo::path)
        .def_readonly("references", &nix::ValidPathInfo::references)
        .def_readonly("registration_time", &nix::ValidPathInfo::registrationTime)
        .def_readonly("ultimate", &nix::ValidPathInfo::ultimate)
        .def_readonly("nar_size", &nix::ValidPathInfo::narSize);

    py::enum_<nix::GCOptions::GCAction>(m, "GCAction")
        .value("GCReturnLive", nix::GCOptions::GCAction::gcReturnLive)
        .value("GCReturnDead", nix::GCOptions::GCAction::gcReturnDead)
        .value("GCDeleteDead", nix::GCOptions::GCAction::gcDeleteDead)
        .value("GCDeleteSpecific", nix::GCOptions::GCAction::gcDeleteSpecific)
        .export_values();

    py::class_<nix::Store, std::shared_ptr<nix::Store>>(m, "Store")
        .def(py::init([](){
            return nix::openStore();
        }))
        .def(
            "collect_garbage",
            [](
                nix::Store& store,
                nix::GCOptions::GCAction action,
                std::optional<nix::StorePathSet> paths_to_delete
            ){
                nix::GCOptions options;
                options.action = action;
                if (paths_to_delete.has_value()) {
                    options.pathsToDelete = std::move(paths_to_delete.value());
                }

                nix::GCResults results;

                // TODO figure out why clang/darwin won't allow casting
                // to a nix::GcStore and remove this nasty hack
                try {
                    dynamic_cast<nix::GcStore&>(store).collectGarbage(options, results);
                } catch (const std::bad_cast& e) {
                    try {
                        dynamic_cast<nix::RemoteStore&>(store).collectGarbage(options, results);
                    } catch (const std::bad_cast& e) {
                        try {
                            dynamic_cast<nix::LocalStore&>(store).collectGarbage(options, results);
                        } catch (const std::bad_cast& e) {
                            try {
                                dynamic_cast<nix::LocalFSStore&>(store).collectGarbage(options, results);
                            } catch (const std::bad_cast& e) {
                                throw nix::UsageError(
                                    "Store '%s' is not a store known to support garbage collection",
                                    store.getUri()
                                );
                            }
                        }
                    }
                }

                return std::make_tuple(std::move(results.paths), results.bytesFreed);
            },
            py::arg("action") = nix::GCOptions::GCAction::gcReturnDead,
            py::arg("paths_to_delete") = py::none(),
            py::call_guard<py::gil_scoped_release>()
        ).def(
            "query_referrers",
            [](
                nix::Store& store,
                nix::StorePath store_path
            ){
                auto results = new nix::StorePathSet();
                store.queryReferrers(store_path, *results);
                return results;
            },
            py::arg("store_path"),
            py::return_value_policy::take_ownership,
            py::call_guard<py::gil_scoped_release>()
        ).def(
            "query_derivation_outputs",
            [](
                nix::Store& store,
                nix::StorePath store_path
            ) {
                return store.queryDerivationOutputs(store_path);
            },
            py::arg("store_path"),
            py::call_guard<py::gil_scoped_release>()
        ).def(
            "query_path_info",
            [](
                nix::Store& store,
                nix::StorePath store_path
            ){
                return store.queryPathInfo(store_path).get_ptr();
            },
            py::arg("store_path"),
            py::call_guard<py::gil_scoped_release>()
        ).def(
            "query_path_info_async",
            [get_event_loop, RuntimeError](
                nix::Store& store,
                nix::StorePath store_path
            ){
                auto pyfuture = get_event_loop().attr("create_future")();

                store.queryPathInfo(
                    store_path,
                    nix::Callback<nix::ref<const nix::ValidPathInfo>>([pyfuture, RuntimeError](
                        std::future<nix::ref<const nix::ValidPathInfo>> f_vpi
                    ) -> void {
                        try {
                            pyfuture.attr("set_result")(f_vpi.get().get_ptr());
                        } catch (const std::exception& e) {
                            // pybind11 doesn't convert exception *arguments* itself
                            pyfuture.attr("set_exception")(RuntimeError(e.what()));
                        }
                    })
                );
                return pyfuture;
            },
            py::arg("store_path"),
            py::call_guard<py::gil_scoped_release>()
        ).def(
            "query_substitutable_paths",
            &nix::Store::querySubstitutablePaths,
            py::call_guard<py::gil_scoped_release>()
        ).def(
            "topo_sort_paths",
            &nix::Store::topoSortPaths,
            py::call_guard<py::gil_scoped_release>()
        );

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
