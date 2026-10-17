// Read-only full dependency-graph diagnostic; no topology or simulator execution.
#define main application_main
#include "../pair-jetty/pair-layer.cc"
#undef main
int main(int argc,char** argv){
    if(argc!=4){std::cerr<<"usage: read-graph input.txt output.csv scan|index\n";return 2;}
    try{
        Layer layer;layer.payloadBudgetBytes=8589934592ULL;layer.weightTaskLimit=1000000;
        layer.dependencyMode=argv[3];Require(layer.dependencyMode=="scan"||layer.dependencyMode=="index","unknown dependency mode");
        layer.Read(argv[1]);std::ofstream graph(argv[2]);Require(bool(graph),"graph output");layer.Graph(graph);graph.close();Require(bool(graph),"graph write");
    }catch(const std::exception& ex){std::cerr<<ex.what()<<'\n';return 2;}
    return 0;
}
