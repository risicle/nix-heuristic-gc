#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#define SYSTEM "x86_64-linux"
#include <nix/store-api.hh>
#include <nix/gc-store.hh>
#include <nix/store-cast.hh>
#undef SYSTEM

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

// struct GCResultsTuple : public nix::GCResults {
//     operator std::tuple<nix::PathSet const&, uint64_t> () {
//         return std::tie(this->paths, this->bytesFreed);
//     };
// };

PYBIND11_MODULE(libstore_wrapper, m) {
    m.doc() = R"pbdoc(
        libnixstore wrapper
        -------------------
    )pbdoc";

    py::class_<nix::StorePath>(m, "StorePath")
        .def(py::init<const std::string &>())
        .def("__str__", &nix::StorePath::to_string)
        .def("__repr__", [](const nix::StorePath& store_path){
            return "StorePath(\"" + std::string(store_path.to_string()) + "\")";
        });

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
                std::optional<nix::StorePathSet*> paths_to_delete
            ){
                nix::GCOptions options;
                options.action = action;
                if (paths_to_delete.has_value()) {
                    options.pathsToDelete = std::move(*paths_to_delete.value());
                }

                nix::GCResults results;

                nix::require<nix::GcStore>(store).collectGarbage(options, results);

                return std::make_tuple(std::move(results.paths), results.bytesFreed);
            },
            py::arg("action") = nix::GCOptions::GCAction::gcReturnDead,
            py::arg("paths_to_delete") = py::none()
        )
        .def(
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
            py::return_value_policy::take_ownership
        ).def(
            "query_substitutable_paths",
            &nix::Store::querySubstitutablePaths
        );

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
