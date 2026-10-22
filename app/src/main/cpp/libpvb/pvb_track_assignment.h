#pragma once
#include <algorithm>
#include <cmath>
namespace pvb {
namespace assignment52 {
constexpr int Observations=6,Tracks=12,Columns=Tracks+Observations;
// phase is at the immediately preceding hop, including every held-hop advance.
// frequency/amplitude may still be the last measured values after a dropout.
struct State {double frequency=0,phase=0,amplitude=0,life=1;int missing=0;};
// Rectangular minimum-cost one-to-one assignment. Private birth columns ensure
// every observation can decline an old track. Fixed storage, no audio allocation.
inline void minimum(const double cost[Observations][Columns],int rows,int columns,int* result) {
    double u[Observations+1]={},v[Columns+1]={};int p[Columns+1]={},way[Columns+1]={};
    for(int i=1;i<=rows;++i) {
        p[0]=i;int j0=0;double distance[Columns+1];bool used[Columns+1]={};
        std::fill(distance,distance+Columns+1,1e100);
        do {
            used[j0]=true;const int i0=p[j0];double delta=1e100;int j1=0;
            for(int j=1;j<=columns;++j) if(!used[j]) {
                const double current=cost[i0-1][j-1]-u[i0]-v[j];
                if(current<distance[j]) {distance[j]=current;way[j]=j0;}
                if(distance[j]<delta) {delta=distance[j];j1=j;}
            }
            for(int j=0;j<=columns;++j) {if(used[j]) {u[p[j]]+=delta;v[j]-=delta;}else distance[j]-=delta;}
            j0=j1;
        } while(p[j0]!=0);
        do {const int j1=way[j0];p[j0]=p[j1];j0=j1;}while(j0);
    }
    std::fill(result,result+rows,-1);
    for(int j=1;j<=columns;++j) if(p[j]) result[p[j]-1]=j-1;
}
inline double cost(const State& observed,const State& old,double predictedFrequency) {
    constexpr double pi=3.14159265358979323846,hop=16./3000;
    if(!std::isfinite(observed.frequency) || !std::isfinite(old.frequency) ||
       !std::isfinite(observed.phase) || !std::isfinite(old.phase) ||
       !std::isfinite(observed.amplitude) || !std::isfinite(old.amplitude) ||
       !std::isfinite(old.life) || !std::isfinite(predictedFrequency) || observed.frequency<=0 || old.frequency<=0 || predictedFrequency<=0 ||
       observed.amplitude<0 || old.amplitude<0 || old.missing<0) return 1e6;
    const double difference=observed.frequency-predictedFrequency;
    if(old.life<=0 || std::abs(difference)>=.1*observed.frequency) return 1e6;
    const double predicted=old.phase+pi*(old.frequency+observed.frequency)*hop;
    const double phase=std::atan2(std::sin(observed.phase-predicted),std::cos(observed.phase-predicted));
    const double frequency=difference/(.1*observed.frequency);
    const double amplitude=std::min(3.,std::abs(std::log((observed.amplitude+1e-9)/(old.amplitude+1e-9))));
    return frequency*frequency+.08*(phase/pi)*(phase/pi)+.04*amplitude*amplitude+.01*old.missing;
}
inline double cost(const State& observed,const State& old) {return cost(observed,old,old.frequency);}
inline void match(const State* observed,int count,const State* old,int tracks,int* result,const double* prediction=nullptr) {
    double costs[Observations][Columns]={};
    for(int i=0;i<count;++i) {
        for(int j=0;j<tracks;++j) costs[i][j]=cost(observed[i],old[j],prediction?prediction[j]:old[j].frequency);
        for(int j=0;j<count;++j) costs[i][tracks+j]=j==i?1.5:1e6;
    }
    minimum(costs,count,tracks+count,result);
    for(int i=0;i<count;++i) if(result[i]>=tracks) result[i]=-1;
}
}
}
